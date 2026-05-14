import logging
import string
from datetime import date, timedelta

from app.db import get_db
from app.email.sender import send_email

log = logging.getLogger(__name__)

_ALLOWED_VARS = {
    "event_name", "event_description", "deadline",
    "sport_name", "league", "league_website",
    "family_last_name", "days_before",
}


def run_daily_job() -> None:
    log.info("Running daily email job for %s", date.today())
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT days_before FROM reminder_intervals ORDER BY days_before")
            intervals = [r[0] for r in cur.fetchall()]

    if not intervals:
        log.warning("No reminder intervals configured — skipping.")
        return

    for days_before in intervals:
        target = date.today() + timedelta(days=days_before)
        _process_interval(days_before, target)


def _process_interval(days_before: int, target_date: date) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT csd.id, csd.event_name, csd.event_description, csd.deadline,
                       s.id AS sport_id, s.name, s.league, s.league_website
                FROM critical_sport_dates csd
                JOIN sport s ON s.id = csd.sport_id
                WHERE csd.deadline = %s
                """,
                (target_date,),
            )
            events = cur.fetchall()

    for event in events:
        (csd_id, event_name, event_description, deadline,
         sport_id, sport_name, league, league_website) = event

        template = _resolve_template(csd_id, sport_id)
        if template is None:
            log.warning(
                "No email template found for event %s (sport_date_id=%s) — skipping.",
                event_name, csd_id,
            )
            continue

        tmpl_subject, tmpl_body = template
        _notify_all_families(
            csd_id=csd_id,
            days_before=days_before,
            tmpl_subject=tmpl_subject,
            tmpl_body=tmpl_body,
            event_vars={
                "event_name": event_name,
                "event_description": event_description or "",
                "deadline": deadline.strftime("%B %d, %Y"),
                "sport_name": sport_name,
                "league": league,
                "league_website": league_website or "",
                "days_before": str(days_before),
            },
        )


def _resolve_template(sport_date_id: int, sport_id: int):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT subject, body_text FROM email_templates "
                "WHERE scope = 'event' AND sport_date_id = %s",
                (sport_date_id,),
            )
            row = cur.fetchone()
            if row:
                return row

            cur.execute(
                "SELECT subject, body_text FROM email_templates "
                "WHERE scope = 'sport' AND sport_id = %s",
                (sport_id,),
            )
            row = cur.fetchone()
            if row:
                return row

            cur.execute(
                "SELECT subject, body_text FROM email_templates WHERE scope = 'global'"
            )
            return cur.fetchone()


def _notify_all_families(
    csd_id: int, days_before: int, tmpl_subject: str, tmpl_body: str, event_vars: dict
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, last_name, email FROM family")
            families = cur.fetchall()

    for family_id, last_name, email in families:
        vars_ = {**event_vars, "family_last_name": last_name}
        try:
            subject = substitute_vars(tmpl_subject, vars_)
            body = substitute_vars(tmpl_body, vars_)
        except KeyError as exc:
            log.error("Unknown template variable %s — skipping family %s", exc, email)
            continue

        _send_with_dedup(
            family_id=family_id,
            csd_id=csd_id,
            days_before=days_before,
            email=email,
            subject=subject,
            body=body,
        )


def _send_with_dedup(
    family_id: int, csd_id: int, days_before: int,
    email: str, subject: str, body: str,
) -> None:
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                INSERT INTO notification_log
                    (family_id, sport_date_id, days_before, recipient_email, subject, status)
                VALUES (%s, %s, %s, %s, %s, 'sent')
                ON CONFLICT (family_id, sport_date_id, days_before) DO NOTHING
                RETURNING id
                """,
                (family_id, csd_id, days_before, email, subject),
            )
            row = cur.fetchone()

        if row is None:
            return  # already sent

        log_id = row[0]
        try:
            send_email(email, subject, body)
        except Exception as exc:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE notification_log SET status='failed', error_message=%s WHERE id=%s",
                    (str(exc), log_id),
                )
            log.error("Failed to send to %s: %s", email, exc)


def substitute_vars(template: str, vars_: dict[str, str]) -> str:
    unknown = {
        k for k in _extract_vars(template) if k not in _ALLOWED_VARS
    }
    if unknown:
        raise KeyError(f"Unknown variable(s) in template: {unknown}")
    return template.format_map(vars_)


def _extract_vars(text: str) -> set[str]:
    return {
        field_name
        for _, field_name, _, _ in string.Formatter().parse(text)
        if field_name is not None
    }
