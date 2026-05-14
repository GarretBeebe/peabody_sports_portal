import os
from datetime import timedelta


class Config:
    # Raises KeyError on startup if not set — no insecure fallback
    SECRET_KEY = os.environ["SECRET_KEY"]
    DATABASE_URL = os.environ["DATABASE_URL"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Strict"
    # Only transmit session cookie over HTTPS; set FLASK_ENV=development to disable
    SESSION_COOKIE_SECURE = os.environ.get("FLASK_ENV", "production") != "development"
    WTF_CSRF_ENABLED = True

    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("PERMANENT_SESSION_LIFETIME_HOURS", 8))
    )

    # Reject uploads larger than 16 MB before they reach route handlers
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    SCHEDULER_HOUR = int(os.environ.get("SCHEDULER_HOUR", 7))
