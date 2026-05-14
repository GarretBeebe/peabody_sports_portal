import pytest
from datetime import date, timedelta
from unittest.mock import patch

from app.email.pipeline import substitute_vars, run_daily_job, _resolve_template
from app.db import get_db


def _insert_family(last_name, email):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO family (last_name, email) VALUES (%s, %s) RETURNING id",
                (last_name, email),
            )
            return cur.fetchone()[0]


def _insert_sport(name):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sport (name, league) VALUES (%s, 'Test League') RETURNING id",
                (name,),
            )
            return cur.fetchone()[0]


def _insert_event(sport_id, event_name, deadline):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO critical_sport_dates (sport_id, event_name, deadline) "
                "VALUES (%s, %s, %s) RETURNING id",
                (sport_id, event_name, deadline),
            )
            return cur.fetchone()[0]


def _insert_template(scope, subject, body, sport_id=None, sport_date_id=None):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO email_templates (scope, sport_id, sport_date_id, subject, body_text) "
                "VALUES (%s, %s, %s, %s, %s) RETURNING id",
                (scope, sport_id, sport_date_id, subject, body),
            )
            return cur.fetchone()[0]


def _insert_interval(days_before):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO reminder_intervals (days_before) VALUES (%s)", (days_before,)
            )


# ── substitute_vars ───────────────────────────────────────────────────────────

class TestSubstituteVars:
    def test_replaces_known_variables(self, app):
        with app.app_context():
            result = substitute_vars(
                "Hello {family_last_name}, deadline is {deadline}.",
                {"family_last_name": "Smith", "deadline": "May 15, 2026"},
            )
            assert result == "Hello Smith, deadline is May 15, 2026."

    def test_raises_on_unknown_variable(self, app):
        with app.app_context():
            with pytest.raises(KeyError):
                substitute_vars("Hello {unknown_var}!", {"unknown_var": "x"})

    def test_empty_optional_vars(self, app):
        with app.app_context():
            result = substitute_vars(
                "Event: {event_name}, Notes: {event_description}",
                {"event_name": "Tryouts", "event_description": ""},
            )
            assert "Tryouts" in result


# ── resolve_template ──────────────────────────────────────────────────────────

class TestResolveTemplate:
    def test_global_fallback(self, app):
        with app.app_context():
            sport_id = _insert_sport("Soccer")
            event_id = _insert_event(sport_id, "Tryouts", date.today() + timedelta(days=7))
            _insert_template("global", "Global Subject", "Global Body")

            result = _resolve_template(event_id, sport_id)
            assert result is not None
            assert result[0] == "Global Subject"

    def test_sport_overrides_global(self, app):
        with app.app_context():
            sport_id = _insert_sport("Baseball")
            event_id = _insert_event(sport_id, "Registration", date.today() + timedelta(days=7))
            _insert_template("global", "Global Subject", "Global Body")
            _insert_template("sport", "Sport Subject", "Sport Body", sport_id=sport_id)

            result = _resolve_template(event_id, sport_id)
            assert result[0] == "Sport Subject"

    def test_event_overrides_sport_and_global(self, app):
        with app.app_context():
            sport_id = _insert_sport("Basketball")
            event_id = _insert_event(sport_id, "Draft", date.today() + timedelta(days=7))
            _insert_template("global", "Global Subject", "Global Body")
            _insert_template("sport", "Sport Subject", "Sport Body", sport_id=sport_id)
            _insert_template("event", "Event Subject", "Event Body", sport_date_id=event_id)

            result = _resolve_template(event_id, sport_id)
            assert result[0] == "Event Subject"

    def test_returns_none_when_no_template(self, app):
        with app.app_context():
            sport_id = _insert_sport("Tennis")
            event_id = _insert_event(sport_id, "Registration", date.today() + timedelta(days=7))

            result = _resolve_template(event_id, sport_id)
            assert result is None


# ── deduplication ─────────────────────────────────────────────────────────────

class TestDeduplication:
    def test_does_not_send_twice(self, app):
        with app.app_context():
            sport_id = _insert_sport("Football")
            target = date.today() + timedelta(days=7)
            event_id = _insert_event(sport_id, "Signups", target)
            _insert_family("Jones", "jones@test.com")
            _insert_interval(7)
            _insert_template(
                "global",
                "Reminder: {event_name}",
                "Hi {family_last_name}, deadline is {deadline} in {days_before} days.\n"
                "Sport: {sport_name}, League: {league}, Site: {league_website}",
            )

            sent_emails = []
            with patch("app.email.pipeline.send_email", side_effect=lambda *a, **kw: sent_emails.append(a)):
                run_daily_job()
                run_daily_job()

            assert len(sent_emails) == 1

    def test_sends_to_all_families(self, app):
        with app.app_context():
            sport_id = _insert_sport("Volleyball")
            target = date.today() + timedelta(days=7)
            event_id = _insert_event(sport_id, "Tryouts", target)
            _insert_family("Smith", "smith@test.com")
            _insert_family("Lee", "lee@test.com")
            _insert_interval(7)
            _insert_template(
                "global",
                "Reminder: {event_name}",
                "Hi {family_last_name}, {deadline}, {days_before} days, "
                "{sport_name}, {league}, {league_website}, {event_description}",
            )

            sent_emails = []
            with patch("app.email.pipeline.send_email", side_effect=lambda *a, **kw: sent_emails.append(a)):
                run_daily_job()

            recipients = {e[0] for e in sent_emails}
            assert recipients == {"smith@test.com", "lee@test.com"}
