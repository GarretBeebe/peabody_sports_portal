"""
Test fixtures. Requires DATABASE_URL to point to a running Postgres instance.
Run inside the container: docker compose exec web python -m pytest tests/
Each test gets a clean slate via TRUNCATE between runs.
"""
import os
import pytest
import psycopg2


@pytest.fixture(scope="session")
def app():
    os.environ.setdefault("DATABASE_URL", os.environ["DATABASE_URL"])
    os.environ.setdefault("SECRET_KEY", "test-secret-key")
    os.environ.setdefault("SMTP_HOST", "")

    from app import create_app
    application = create_app()
    application.config["TESTING"] = True
    application.config["WTF_CSRF_ENABLED"] = False
    return application


@pytest.fixture(scope="session")
def _apply_schema(app):
    from app.extensions import db_pool
    conn = db_pool.getconn()
    conn.autocommit = True
    with conn.cursor() as cur:
        with open("migrations/001_initial.sql") as f:
            cur.execute(f.read())
    db_pool.putconn(conn)


@pytest.fixture(autouse=True)
def clean_db(app, _apply_schema):
    yield
    from app.extensions import db_pool
    conn = db_pool.getconn()
    with conn:
        with conn.cursor() as cur:
            cur.execute(
                "TRUNCATE notification_log, email_templates, critical_sport_dates, "
                "student, sport, family, admin_users, reminder_intervals "
                "RESTART IDENTITY CASCADE"
            )
    db_pool.putconn(conn)


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db(app):
    from app.db import get_db
    return get_db
