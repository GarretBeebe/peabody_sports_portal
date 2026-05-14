from datetime import date, timedelta

from app.db import get_db


def _seed_sport_and_event(deadline):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO sport (name, league) VALUES ('Test Sport', 'Test League') RETURNING id"
            )
            sport_id = cur.fetchone()[0]
            cur.execute(
                "INSERT INTO critical_sport_dates (sport_id, event_name, deadline) "
                "VALUES (%s, 'Test Event', %s)",
                (sport_id, deadline),
            )


class TestPublicIndex:
    def test_returns_200(self, app, client):
        with app.app_context():
            response = client.get("/")
            assert response.status_code == 200

    def test_shows_upcoming_event(self, app, client):
        with app.app_context():
            future = date.today() + timedelta(days=10)
            _seed_sport_and_event(future)
            response = client.get("/")
            assert b"Test Event" in response.data

    def test_hides_past_event(self, app, client):
        with app.app_context():
            past = date.today() - timedelta(days=1)
            _seed_sport_and_event(past)
            response = client.get("/")
            assert b"Test Event" not in response.data

    def test_no_auth_required(self, app, client):
        with app.app_context():
            response = client.get("/")
            assert response.status_code == 200
            assert b"Admin Login" in response.data or b"Peabody" in response.data
