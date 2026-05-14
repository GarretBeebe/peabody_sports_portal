"""CSV import logic — no HTTP layer; independently unit-testable."""
import csv
import io
import re
from datetime import date

from app.db import get_db

_EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def _reader(file_storage):
    text = io.StringIO(file_storage.read().decode("utf-8-sig"))
    return csv.DictReader(text)


def _require_cols(reader, required, entity):
    missing = [c for c in required if c not in reader.fieldnames]
    if missing:
        return [f"Missing required columns: {', '.join(missing)}"]
    return []


# ── Families ──────────────────────────────────────────────────────────────────

def import_families(file_storage):
    reader = _reader(file_storage)
    errors = _require_cols(reader, ["last_name", "email"], "family")
    if errors:
        return errors

    rows, row_errors = [], []
    for i, row in enumerate(reader, start=2):
        last_name = row.get("last_name", "").strip()
        email = row.get("email", "").strip().lower()
        valid = True
        if not last_name:
            row_errors.append(f"Row {i}: last_name is required.")
            valid = False
        if not email or not _EMAIL_RE.match(email):
            row_errors.append(f"Row {i}: invalid email '{email}'.")
            valid = False
        if valid:
            rows.append((last_name, email))

    if row_errors:
        return row_errors

    with get_db() as conn:
        with conn.cursor() as cur:
            for last_name, email in rows:
                cur.execute(
                    """
                    INSERT INTO family (last_name, email)
                    VALUES (%s, %s)
                    ON CONFLICT (email) DO UPDATE
                      SET last_name = EXCLUDED.last_name, updated_at = NOW()
                    """,
                    (last_name, email),
                )
    return []


# ── Students ──────────────────────────────────────────────────────────────────

def import_students(file_storage):
    reader = _reader(file_storage)
    errors = _require_cols(
        reader, ["family_email", "first_name", "last_name", "grade", "teacher"], "student"
    )
    if errors:
        return errors

    # Pre-load family email → id map
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT email, id FROM family")
            family_map = {r[0]: r[1] for r in cur.fetchall()}

    rows, row_errors = [], []
    for i, row in enumerate(reader, start=2):
        family_email = row.get("family_email", "").strip().lower()
        first_name = row.get("first_name", "").strip()
        last_name = row.get("last_name", "").strip()
        grade_raw = row.get("grade", "").strip()
        teacher = row.get("teacher", "").strip()

        family_id = family_map.get(family_email)
        if not family_id:
            row_errors.append(f"Row {i}: family_email '{family_email}' not found.")
        if not first_name:
            row_errors.append(f"Row {i}: first_name is required.")
        if not last_name:
            row_errors.append(f"Row {i}: last_name is required.")
        if not teacher:
            row_errors.append(f"Row {i}: teacher is required.")

        try:
            grade = int(grade_raw)
            if not (0 <= grade <= 12):
                raise ValueError
        except ValueError:
            row_errors.append(f"Row {i}: grade must be an integer 0–12 (got '{grade_raw}').")
            grade = None

        if family_id and first_name and last_name and teacher and grade is not None:
            rows.append((family_id, first_name, last_name, grade, teacher))

    if row_errors:
        return row_errors

    with get_db() as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO student (family_id, first_name, last_name, grade, teacher) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    r,
                )
    return []


# ── Sports ────────────────────────────────────────────────────────────────────

def import_sports(file_storage):
    reader = _reader(file_storage)
    errors = _require_cols(reader, ["name", "league"], "sport")
    if errors:
        return errors

    rows, row_errors = [], []
    for i, row in enumerate(reader, start=2):
        name = row.get("name", "").strip()
        league = row.get("league", "").strip()
        website = row.get("league_website", "").strip() or None

        if not name:
            row_errors.append(f"Row {i}: name is required.")
        if not league:
            row_errors.append(f"Row {i}: league is required.")

        if name and league:
            rows.append((name, league, website))

    if row_errors:
        return row_errors

    with get_db() as conn:
        with conn.cursor() as cur:
            for name, league, website in rows:
                cur.execute(
                    """
                    INSERT INTO sport (name, league, league_website)
                    VALUES (%s, %s, %s)
                    ON CONFLICT (name) DO UPDATE
                      SET league = EXCLUDED.league,
                          league_website = EXCLUDED.league_website,
                          updated_at = NOW()
                    """,
                    (name, league, website),
                )
    return []


# ── Critical Sport Dates ───────────────────────────────────────────────────────

def import_dates(file_storage):
    reader = _reader(file_storage)
    errors = _require_cols(reader, ["sport_name", "event_name", "deadline"], "critical_sport_dates")
    if errors:
        return errors

    # Pre-load sport name → id map
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT name, id FROM sport")
            sport_map = {r[0]: r[1] for r in cur.fetchall()}

    rows, row_errors = [], []
    for i, row in enumerate(reader, start=2):
        sport_name = row.get("sport_name", "").strip()
        event_name = row.get("event_name", "").strip()
        deadline_raw = row.get("deadline", "").strip()
        description = row.get("event_description", "").strip() or None

        sport_id = sport_map.get(sport_name)
        if not sport_id:
            row_errors.append(f"Row {i}: sport_name '{sport_name}' not found.")
        if not event_name:
            row_errors.append(f"Row {i}: event_name is required.")

        try:
            deadline = date.fromisoformat(deadline_raw)
        except ValueError:
            row_errors.append(f"Row {i}: deadline must be YYYY-MM-DD (got '{deadline_raw}').")
            deadline = None

        if sport_id and event_name and deadline:
            rows.append((sport_id, event_name, description, deadline))

    if row_errors:
        return row_errors

    with get_db() as conn:
        with conn.cursor() as cur:
            for r in rows:
                cur.execute(
                    "INSERT INTO critical_sport_dates "
                    "(sport_id, event_name, event_description, deadline) "
                    "VALUES (%s, %s, %s, %s)",
                    r,
                )
    return []
