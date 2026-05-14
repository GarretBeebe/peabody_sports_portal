from urllib.parse import urlparse

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import UserMixin, current_user, login_required, login_user, logout_user

from app.auth.forms import LoginForm
from app.db import get_db
from app.extensions import bcrypt

auth_bp = Blueprint("auth", __name__)


class AdminUser(UserMixin):
    def __init__(self, id, username, email, is_active):
        self.id = id
        self.username = username
        self.email = email
        self._is_active = is_active

    @property
    def is_active(self):
        return self._is_active


def load_user(user_id):
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


@auth_bp.route("/admin/login", methods=["GET", "POST"])
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
            next_url = request.args.get("next", "")
            parsed = urlparse(next_url)
            if parsed.netloc or parsed.scheme:
                next_url = ""
            return redirect(next_url or url_for("admin.dashboard"))

        flash("Invalid username or password.", "danger")

    return render_template("admin/login.html", form=form)


@auth_bp.route("/admin/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.login"))
