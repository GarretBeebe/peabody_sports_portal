import logging
import smtplib
from email.mime.text import MIMEText

from flask import current_app

log = logging.getLogger(__name__)


def send_email(to_addr: str, subject: str, body: str) -> None:
    cfg = current_app.config
    host = cfg["SMTP_HOST"]
    port = cfg["SMTP_PORT"]
    user = cfg["SMTP_USER"]
    password = cfg["SMTP_PASSWORD"]
    from_addr = cfg["SMTP_FROM"]
    use_tls = cfg["SMTP_USE_TLS"]

    if not host:
        log.warning("SMTP_HOST not configured — email not sent to %s", to_addr)
        return

    msg = MIMEText(body, "plain", "utf-8")
    msg["Subject"] = subject
    msg["From"] = from_addr
    msg["To"] = to_addr

    with smtplib.SMTP(host, port) as server:
        server.ehlo()
        if use_tls:
            server.starttls()
            server.ehlo()
        if user:
            server.login(user, password)
        server.send_message(msg)

    log.info("Email sent to %s — %s", to_addr, subject)
