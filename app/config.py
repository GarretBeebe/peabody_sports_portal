import os
from datetime import timedelta


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "dev-insecure-key-change-me")
    DATABASE_URL = os.environ["DATABASE_URL"]

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    WTF_CSRF_ENABLED = True

    PERMANENT_SESSION_LIFETIME = timedelta(
        hours=int(os.environ.get("PERMANENT_SESSION_LIFETIME_HOURS", 8))
    )

    SMTP_HOST = os.environ.get("SMTP_HOST", "")
    SMTP_PORT = int(os.environ.get("SMTP_PORT", 587))
    SMTP_USER = os.environ.get("SMTP_USER", "")
    SMTP_PASSWORD = os.environ.get("SMTP_PASSWORD", "")
    SMTP_FROM = os.environ.get("SMTP_FROM", "")
    SMTP_USE_TLS = os.environ.get("SMTP_USE_TLS", "true").lower() == "true"

    SCHEDULER_HOUR = int(os.environ.get("SCHEDULER_HOUR", 7))
