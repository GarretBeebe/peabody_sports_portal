import logging
from urllib.parse import urljoin, urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm
from app.db import get_db
from app.extensions import bcrypt, limiter

log = logging.getLogger(__name__)

auth_bp = Blueprint("auth", __name__)


class AdminUser(UserMixin):
    def __init__(self, id: int, username: str, email: str, is_active: bool) -> None:
        self.id = id
        self.username = username
        self.email = email
        self._is_active = is_active

    @property
    def is_active(self) -> bool:
        return self._is_active


def load_user(user_id: str) -> "AdminUser | None":
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, username, email, is_active FROM admin_users WHERE id = %s",
                (int(user_id),),
            )
            row = cur.fetchone()
    if row is None:
        return None
    return AdminUser(*row)


def _is_safe_redirect(url: str) -> bool:
    """Return True only if url resolves to the same host as the current request."""
    if not url:
        return False
    ref = urlparse(request.host_url)
    test = urlparse(urljoin(request.host_url, url))
    return test.scheme in ("http", "https") and ref.netloc == test.netloc


@auth_bp.route("/admin/login", methods=["GET", "POST"])
@limiter.limit("10 per minute")
def login():
    if current_user.is_authenticated:
        return redirect(url_for("admin.dashboard"))

    form = LoginForm()
    if form.validate_on_submit():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT id, username, email, is_active, password_hash "
                    "FROM admin_users WHERE username = %s",
                    (form.username.data,),
                )
                row = cur.fetchone()

        valid = row and row[3] and bcrypt.check_password_hash(row[4], form.password.data)
        if valid:
            user = AdminUser(row[0], row[1], row[2], row[3])
            login_user(user)
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE admin_users SET last_login_at = NOW() WHERE id = %s",
                        (user.id,),
                    )
            log.info("Successful login: user=%s ip=%s", user.username, request.remote_addr)
            next_url = request.args.get("next", "")
            return redirect(next_url if _is_safe_redirect(next_url) else url_for("admin.dashboard"))

        log.warning("Failed login attempt: username=%s ip=%s", form.username.data, request.remote_addr)
        flash("Invalid username or password.", "danger")

    return render_template("admin/login.html", form=form)


@auth_bp.route("/admin/logout")
@login_required
def logout():
    log.info("Logout: user=%s ip=%s", current_user.username, request.remote_addr)
    logout_user()
    return redirect(url_for("auth.login"))
