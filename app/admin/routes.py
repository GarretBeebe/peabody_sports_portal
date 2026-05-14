import logging
from datetime import date

from flask import Blueprint, flash, redirect, render_template, request, url_for
from flask_login import login_required

log = logging.getLogger(__name__)

from app.db import get_db

admin_bp = Blueprint("admin", __name__, url_prefix="/admin")


# ── Dashboard ─────────────────────────────────────────────────────────────────

@admin_bp.route("/")
@login_required
def dashboard():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM family")
            family_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM student")
            student_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM sport")
            sport_count = cur.fetchone()[0]
            cur.execute(
                "SELECT COUNT(*) FROM critical_sport_dates WHERE deadline >= CURRENT_DATE"
            )
            upcoming_count = cur.fetchone()[0]
    return render_template(
        "admin/dashboard.html",
        family_count=family_count,
        student_count=student_count,
        sport_count=sport_count,
        upcoming_count=upcoming_count,
    )


# ── Families ──────────────────────────────────────────────────────────────────

@admin_bp.route("/families")
@login_required
def families_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, last_name, email FROM family ORDER BY last_name, email")
            rows = cur.fetchall()
    return render_template("admin/families/list.html", families=rows)


@admin_bp.route("/families/new", methods=["GET", "POST"])
@login_required
def families_new():
    from app.admin.forms import FamilyForm
    form = FamilyForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO family (last_name, email) VALUES (%s, %s)",
                        (form.last_name.data.strip(), form.email.data.strip().lower()),
                    )
            flash("Family added.", "success")
            return redirect(url_for("admin.families_list"))
        except Exception as exc:
            _flash_db_error(exc, "A family with that email already exists.")
    return render_template("admin/families/form.html", form=form, title="Add Family")


@admin_bp.route("/families/<int:id>/edit", methods=["GET", "POST"])
@login_required
def families_edit(id):
    from app.admin.forms import FamilyForm
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, last_name, email FROM family WHERE id = %s", (id,))
            row = cur.fetchone()
    if row is None:
        flash("Family not found.", "warning")
        return redirect(url_for("admin.families_list"))

    form = FamilyForm(data={"last_name": row[1], "email": row[2]})
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE family SET last_name=%s, email=%s, updated_at=NOW() WHERE id=%s",
                        (form.last_name.data.strip(), form.email.data.strip().lower(), id),
                    )
            flash("Family updated.", "success")
            return redirect(url_for("admin.families_list"))
        except Exception as exc:
            _flash_db_error(exc, "A family with that email already exists.")
    return render_template("admin/families/form.html", form=form, title="Edit Family")


@admin_bp.route("/families/<int:id>/delete", methods=["POST"])
@login_required
def families_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM family WHERE id = %s", (id,))
    flash("Family deleted.", "success")
    return redirect(url_for("admin.families_list"))


@admin_bp.route("/families/upload", methods=["GET", "POST"])
@login_required
def families_upload():
    if request.method == "POST":
        f = _get_csv_upload()
        if f is None:
            return redirect(request.url)
        from app.admin.csv_import import import_families
        errors = import_families(f)
        if errors:
            return render_template("admin/upload_errors.html", errors=errors, entity="Families")
        flash("Families imported successfully.", "success")
        return redirect(url_for("admin.families_list"))
    return render_template("admin/families/upload.html")


# ── Students ──────────────────────────────────────────────────────────────────

@admin_bp.route("/students")
@login_required
def students_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT s.id, s.first_name, s.last_name,
                       s.grade, s.teacher, f.last_name, f.email
                FROM student s
                JOIN family f ON f.id = s.family_id
                ORDER BY s.last_name, s.first_name
                """
            )
            rows = cur.fetchall()
    return render_template("admin/students/list.html", students=rows)


@admin_bp.route("/students/new", methods=["GET", "POST"])
@login_required
def students_new():
    from app.admin.forms import StudentForm
    form = StudentForm()
    _populate_family_choices(form)
    if form.validate_on_submit():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO student (family_id, first_name, last_name, grade, teacher) "
                    "VALUES (%s, %s, %s, %s, %s)",
                    (
                        form.family_id.data,
                        form.first_name.data.strip(),
                        form.last_name.data.strip(),
                        form.grade.data,
                        form.teacher.data.strip(),
                    ),
                )
        flash("Student added.", "success")
        return redirect(url_for("admin.students_list"))
    return render_template("admin/students/form.html", form=form, title="Add Student")


@admin_bp.route("/students/<int:id>/edit", methods=["GET", "POST"])
@login_required
def students_edit(id):
    from app.admin.forms import StudentForm
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, family_id, first_name, last_name, grade, teacher "
                "FROM student WHERE id = %s",
                (id,),
            )
            row = cur.fetchone()
    if row is None:
        flash("Student not found.", "warning")
        return redirect(url_for("admin.students_list"))

    form = StudentForm(
        data={
            "family_id": row[1],
            "first_name": row[2],
            "last_name": row[3],
            "grade": row[4],
            "teacher": row[5],
        }
    )
    _populate_family_choices(form)
    if form.validate_on_submit():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE student SET family_id=%s, first_name=%s, last_name=%s, "
                    "grade=%s, teacher=%s, updated_at=NOW() WHERE id=%s",
                    (
                        form.family_id.data,
                        form.first_name.data.strip(),
                        form.last_name.data.strip(),
                        form.grade.data,
                        form.teacher.data.strip(),
                        id,
                    ),
                )
        flash("Student updated.", "success")
        return redirect(url_for("admin.students_list"))
    return render_template("admin/students/form.html", form=form, title="Edit Student")


@admin_bp.route("/students/<int:id>/delete", methods=["POST"])
@login_required
def students_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM student WHERE id = %s", (id,))
    flash("Student deleted.", "success")
    return redirect(url_for("admin.students_list"))


@admin_bp.route("/students/upload", methods=["GET", "POST"])
@login_required
def students_upload():
    if request.method == "POST":
        f = _get_csv_upload()
        if f is None:
            return redirect(request.url)
        from app.admin.csv_import import import_students
        errors = import_students(f)
        if errors:
            return render_template("admin/upload_errors.html", errors=errors, entity="Students")
        flash("Students imported successfully.", "success")
        return redirect(url_for("admin.students_list"))
    return render_template("admin/students/upload.html")


# ── Sports ────────────────────────────────────────────────────────────────────

@admin_bp.route("/sports")
@login_required
def sports_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name, league, league_website FROM sport ORDER BY name")
            rows = cur.fetchall()
    return render_template("admin/sports/list.html", sports=rows)


@admin_bp.route("/sports/new", methods=["GET", "POST"])
@login_required
def sports_new():
    from app.admin.forms import SportForm
    form = SportForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO sport (name, league, league_website) VALUES (%s, %s, %s)",
                        (
                            form.name.data.strip(),
                            form.league.data.strip(),
                            form.league_website.data.strip() or None,
                        ),
                    )
            flash("Sport added.", "success")
            return redirect(url_for("admin.sports_list"))
        except Exception as exc:
            _flash_db_error(exc, "A sport with that name already exists.")
    return render_template("admin/sports/form.html", form=form, title="Add Sport")


@admin_bp.route("/sports/<int:id>/edit", methods=["GET", "POST"])
@login_required
def sports_edit(id):
    from app.admin.forms import SportForm
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, name, league, league_website FROM sport WHERE id = %s", (id,)
            )
            row = cur.fetchone()
    if row is None:
        flash("Sport not found.", "warning")
        return redirect(url_for("admin.sports_list"))

    form = SportForm(data={"name": row[1], "league": row[2], "league_website": row[3]})
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE sport SET name=%s, league=%s, league_website=%s, "
                        "updated_at=NOW() WHERE id=%s",
                        (
                            form.name.data.strip(),
                            form.league.data.strip(),
                            form.league_website.data.strip() or None,
                            id,
                        ),
                    )
            flash("Sport updated.", "success")
            return redirect(url_for("admin.sports_list"))
        except Exception as exc:
            _flash_db_error(exc, "A sport with that name already exists.")
    return render_template("admin/sports/form.html", form=form, title="Edit Sport")


@admin_bp.route("/sports/<int:id>/delete", methods=["POST"])
@login_required
def sports_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM sport WHERE id = %s", (id,))
    flash("Sport deleted.", "success")
    return redirect(url_for("admin.sports_list"))


@admin_bp.route("/sports/upload", methods=["GET", "POST"])
@login_required
def sports_upload():
    if request.method == "POST":
        f = _get_csv_upload()
        if f is None:
            return redirect(request.url)
        from app.admin.csv_import import import_sports
        errors = import_sports(f)
        if errors:
            return render_template("admin/upload_errors.html", errors=errors, entity="Sports")
        flash("Sports imported successfully.", "success")
        return redirect(url_for("admin.sports_list"))
    return render_template("admin/sports/upload.html")


# ── Critical Sport Dates ───────────────────────────────────────────────────────

@admin_bp.route("/dates")
@login_required
def dates_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT csd.id, s.name, csd.event_name, csd.deadline, csd.event_description
                FROM critical_sport_dates csd
                JOIN sport s ON s.id = csd.sport_id
                ORDER BY csd.deadline DESC
                """
            )
            rows = cur.fetchall()
    return render_template("admin/dates/list.html", dates=rows, today=date.today())


@admin_bp.route("/dates/new", methods=["GET", "POST"])
@login_required
def dates_new():
    from app.admin.forms import SportDateForm
    form = SportDateForm()
    _populate_sport_choices(form)
    if form.validate_on_submit():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO critical_sport_dates "
                    "(sport_id, event_name, event_description, deadline) "
                    "VALUES (%s, %s, %s, %s)",
                    (
                        form.sport_id.data,
                        form.event_name.data.strip(),
                        form.event_description.data.strip() or None,
                        form.deadline.data,
                    ),
                )
        flash("Event added.", "success")
        return redirect(url_for("admin.dates_list"))
    return render_template("admin/dates/form.html", form=form, title="Add Event")


@admin_bp.route("/dates/<int:id>/edit", methods=["GET", "POST"])
@login_required
def dates_edit(id):
    from app.admin.forms import SportDateForm
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, sport_id, event_name, event_description, deadline "
                "FROM critical_sport_dates WHERE id = %s",
                (id,),
            )
            row = cur.fetchone()
    if row is None:
        flash("Event not found.", "warning")
        return redirect(url_for("admin.dates_list"))

    form = SportDateForm(
        data={
            "sport_id": row[1],
            "event_name": row[2],
            "event_description": row[3],
            "deadline": row[4],
        }
    )
    _populate_sport_choices(form)
    if form.validate_on_submit():
        with get_db() as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "UPDATE critical_sport_dates SET sport_id=%s, event_name=%s, "
                    "event_description=%s, deadline=%s, updated_at=NOW() WHERE id=%s",
                    (
                        form.sport_id.data,
                        form.event_name.data.strip(),
                        form.event_description.data.strip() or None,
                        form.deadline.data,
                        id,
                    ),
                )
        flash("Event updated.", "success")
        return redirect(url_for("admin.dates_list"))
    return render_template("admin/dates/form.html", form=form, title="Edit Event")


@admin_bp.route("/dates/<int:id>/delete", methods=["POST"])
@login_required
def dates_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM critical_sport_dates WHERE id = %s", (id,))
    flash("Event deleted.", "success")
    return redirect(url_for("admin.dates_list"))


@admin_bp.route("/dates/upload", methods=["GET", "POST"])
@login_required
def dates_upload():
    if request.method == "POST":
        f = _get_csv_upload()
        if f is None:
            return redirect(request.url)
        from app.admin.csv_import import import_dates
        errors = import_dates(f)
        if errors:
            return render_template("admin/upload_errors.html", errors=errors, entity="Events")
        flash("Events imported successfully.", "success")
        return redirect(url_for("admin.dates_list"))
    return render_template("admin/dates/upload.html")


# ── Email Templates ────────────────────────────────────────────────────────────

@admin_bp.route("/templates")
@login_required
def templates_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT et.id, et.scope, et.subject,
                       s.name  AS sport_name,
                       csd.event_name AS event_name
                FROM email_templates et
                LEFT JOIN sport s ON s.id = et.sport_id
                LEFT JOIN critical_sport_dates csd ON csd.id = et.sport_date_id
                ORDER BY et.scope, sport_name, event_name
                """
            )
            rows = cur.fetchall()
    return render_template("admin/templates/list.html", templates=rows)


@admin_bp.route("/templates/new", methods=["GET", "POST"])
@login_required
def templates_new():
    from app.admin.forms import EmailTemplateForm
    form = EmailTemplateForm()
    _populate_sport_choices(form, include_blank=True)
    _populate_date_choices(form)
    if form.validate_on_submit():
        scope = form.scope.data
        sport_id = form.sport_id.data if scope == "sport" else None
        sport_date_id = form.sport_date_id.data if scope == "event" else None
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO email_templates "
                        "(scope, sport_id, sport_date_id, subject, body_text) "
                        "VALUES (%s, %s, %s, %s, %s)",
                        (scope, sport_id or None, sport_date_id or None,
                         form.subject.data.strip(), form.body_text.data.strip()),
                    )
            flash("Template saved.", "success")
            return redirect(url_for("admin.templates_list"))
        except Exception as exc:
            _flash_db_error(exc, "A template for that scope/target already exists.")
    return render_template("admin/templates/form.html", form=form, title="Add Template")


@admin_bp.route("/templates/<int:id>/edit", methods=["GET", "POST"])
@login_required
def templates_edit(id):
    from app.admin.forms import EmailTemplateForm
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT id, scope, sport_id, sport_date_id, subject, body_text "
                "FROM email_templates WHERE id = %s",
                (id,),
            )
            row = cur.fetchone()
    if row is None:
        flash("Template not found.", "warning")
        return redirect(url_for("admin.templates_list"))

    form = EmailTemplateForm(
        data={
            "scope": row[1],
            "sport_id": row[2],
            "sport_date_id": row[3],
            "subject": row[4],
            "body_text": row[5],
        }
    )
    _populate_sport_choices(form, include_blank=True)
    _populate_date_choices(form)
    if form.validate_on_submit():
        scope = form.scope.data
        sport_id = form.sport_id.data if scope == "sport" else None
        sport_date_id = form.sport_date_id.data if scope == "event" else None
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE email_templates SET scope=%s, sport_id=%s, sport_date_id=%s, "
                        "subject=%s, body_text=%s, updated_at=NOW() WHERE id=%s",
                        (scope, sport_id or None, sport_date_id or None,
                         form.subject.data.strip(), form.body_text.data.strip(), id),
                    )
            flash("Template updated.", "success")
            return redirect(url_for("admin.templates_list"))
        except Exception as exc:
            _flash_db_error(exc, "A template for that scope/target already exists.")
    return render_template("admin/templates/form.html", form=form, title="Edit Template")


@admin_bp.route("/templates/<int:id>/delete", methods=["POST"])
@login_required
def templates_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM email_templates WHERE id = %s", (id,))
    flash("Template deleted.", "success")
    return redirect(url_for("admin.templates_list"))


# ── Reminder Intervals ────────────────────────────────────────────────────────

@admin_bp.route("/intervals")
@login_required
def intervals_list():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, days_before FROM reminder_intervals ORDER BY days_before")
            rows = cur.fetchall()
    return render_template("admin/intervals/list.html", intervals=rows)


@admin_bp.route("/intervals/new", methods=["GET", "POST"])
@login_required
def intervals_new():
    from app.admin.forms import IntervalForm
    form = IntervalForm()
    if form.validate_on_submit():
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO reminder_intervals (days_before) VALUES (%s)",
                        (form.days_before.data,),
                    )
            flash(f"{form.days_before.data}-day reminder added.", "success")
            return redirect(url_for("admin.intervals_list"))
        except Exception as exc:
            _flash_db_error(exc, "That interval already exists.")
    return render_template("admin/intervals/form.html", form=form, title="Add Reminder Interval")


@admin_bp.route("/intervals/<int:id>/delete", methods=["POST"])
@login_required
def intervals_delete(id):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM reminder_intervals WHERE id = %s", (id,))
    flash("Interval deleted.", "success")
    return redirect(url_for("admin.intervals_list"))


# ── Notification Log ──────────────────────────────────────────────────────────

@admin_bp.route("/log")
@login_required
def notification_log():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT nl.sent_at, nl.recipient_email, nl.subject,
                       nl.days_before, nl.status, nl.error_message,
                       s.name AS sport_name, csd.event_name
                FROM notification_log nl
                JOIN critical_sport_dates csd ON csd.id = nl.sport_date_id
                JOIN sport s ON s.id = csd.sport_id
                ORDER BY nl.sent_at DESC
                LIMIT 500
                """
            )
            rows = cur.fetchall()
    return render_template("admin/log.html", entries=rows)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _flash_db_error(exc: Exception, unique_msg: str) -> None:
    if "unique" in str(exc).lower():
        flash(unique_msg, "danger")
    else:
        log.error("Unexpected database error: %s", exc)
        flash("An unexpected error occurred. Please try again.", "danger")


def _get_csv_upload():
    f = request.files.get("file")
    if not f or not f.filename.endswith(".csv"):
        flash("Please upload a CSV file.", "danger")
        return None
    return f


def _populate_family_choices(form):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, last_name, email FROM family ORDER BY last_name, email")
            rows = cur.fetchall()
    form.family_id.choices = [(r[0], f"{r[1]} ({r[2]})") for r in rows]


def _populate_sport_choices(form, include_blank=False):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT id, name FROM sport ORDER BY name")
            rows = cur.fetchall()
    choices = [(r[0], r[1]) for r in rows]
    if include_blank:
        choices.insert(0, ("", "— select —"))
    form.sport_id.choices = choices


def _populate_date_choices(form):
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT csd.id, s.name || ' — ' || csd.event_name
                FROM critical_sport_dates csd
                JOIN sport s ON s.id = csd.sport_id
                ORDER BY csd.deadline DESC
                """
            )
            rows = cur.fetchall()
    form.sport_date_id.choices = [("", "— select —")] + [(r[0], r[1]) for r in rows]
