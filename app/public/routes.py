from flask import Blueprint, render_template

from app.db import get_db

public_bp = Blueprint("public", __name__)


@public_bp.route("/")
def index():
    with get_db() as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT csd.event_name, csd.event_description, csd.deadline,
                       s.name AS sport_name, s.league_website
                FROM critical_sport_dates csd
                JOIN sport s ON s.id = csd.sport_id
                WHERE csd.deadline >= CURRENT_DATE
                ORDER BY csd.deadline ASC
                """
            )
            events = cur.fetchall()
    return render_template("public/index.html", events=events)
