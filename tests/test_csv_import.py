import io
import pytest
from werkzeug.datastructures import FileStorage

from app.admin.csv_import import import_families, import_sports, import_students, import_dates
from app.db import get_db


def _csv(content: str) -> FileStorage:
    return FileStorage(stream=io.BytesIO(content.encode("utf-8")), filename="test.csv")


def _seed_family(last_name, email):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO family (last_name, email) VALUES (%s, %s) RETURNING id",
                (last_name, email),
            )
            return cur.fetchone()[0]


def _seed_sport(name):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sport (name, league) VALUES (%s, 'Test League') RETURNING id",
                (name,),
            )
            return cur.fetchone()[0]


# ── Families ──────────────────────────────────────────────────────────────────

class TestImportFamilies:
    def test_valid_import(self, app):
        with app.app_context():
            errors = import_families(_csv("last_name,email\nSmith,smith@test.com\n"))
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM family")
                    assert cur.fetchone()[0] == 1

    def test_upserts_existing_email(self, app):
        with app.app_context():
            _seed_family("Old", "same@test.com")
            errors = import_families(_csv("last_name,email\nNew,same@test.com\n"))
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT last_name FROM family WHERE email = 'same@test.com'")
                    assert cur.fetchone()[0] == "New"

    def test_rejects_invalid_email(self, app):
        with app.app_context():
            errors = import_families(_csv("last_name,email\nSmith,not-an-email\n"))
            assert any("invalid email" in e for e in errors)

    def test_rejects_missing_column(self, app):
        with app.app_context():
            errors = import_families(_csv("last_name\nSmith\n"))
            assert any("email" in e for e in errors)

    def test_no_partial_import_on_error(self, app):
        with app.app_context():
            csv_data = "last_name,email\nGood,good@test.com\nBad,not-valid\n"
            errors = import_families(_csv(csv_data))
            assert errors
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM family")
                    assert cur.fetchone()[0] == 0


# ── Students ──────────────────────────────────────────────────────────────────

class TestImportStudents:
    def test_valid_import(self, app):
        with app.app_context():
            _seed_family("Smith", "smith@test.com")
            errors = import_students(
                _csv("family_email,first_name,last_name,grade,teacher\n"
                     "smith@test.com,Alice,Smith,3,Johnson\n")
            )
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM student")
                    assert cur.fetchone()[0] == 1

    def test_rejects_unknown_family_email(self, app):
        with app.app_context():
            errors = import_students(
                _csv("family_email,first_name,last_name,grade,teacher\n"
                     "nobody@test.com,Alice,Smith,3,Johnson\n")
            )
            assert any("not found" in e for e in errors)

    def test_rejects_invalid_grade(self, app):
        with app.app_context():
            _seed_family("Lee", "lee@test.com")
            errors = import_students(
                _csv("family_email,first_name,last_name,grade,teacher\n"
                     "lee@test.com,Bob,Lee,99,Davis\n")
            )
            assert any("grade" in e for e in errors)


# ── Sports ────────────────────────────────────────────────────────────────────

class TestImportSports:
    def test_valid_import(self, app):
        with app.app_context():
            errors = import_sports(_csv("name,league\nSoccer,City League\n"))
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM sport")
                    assert cur.fetchone()[0] == 1

    def test_upserts_existing_sport(self, app):
        with app.app_context():
            _seed_sport("Soccer")
            errors = import_sports(_csv("name,league\nSoccer,New League\n"))
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM sport")
                    assert cur.fetchone()[0] == 1


# ── Critical Sport Dates ───────────────────────────────────────────────────────

class TestImportDates:
    def test_valid_import(self, app):
        with app.app_context():
            _seed_sport("Baseball")
            errors = import_dates(
                _csv("sport_name,event_name,deadline\nBaseball,Tryouts,2026-09-01\n")
            )
            assert errors == []
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT COUNT(*) FROM critical_sport_dates")
                    assert cur.fetchone()[0] == 1

    def test_rejects_unknown_sport(self, app):
        with app.app_context():
            errors = import_dates(
                _csv("sport_name,event_name,deadline\nUnknownSport,Tryouts,2026-09-01\n")
            )
            assert any("not found" in e for e in errors)

    def test_rejects_invalid_date_format(self, app):
        with app.app_context():
            _seed_sport("Tennis")
            errors = import_dates(
                _csv("sport_name,event_name,deadline\nTennis,Signups,09/01/2026\n")
            )
            assert any("deadline" in e for e in errors)
