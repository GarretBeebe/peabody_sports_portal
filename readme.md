# Peabody Sports Portal

A self-hosted web application that publishes upcoming sports deadlines and automatically emails families before they arrive.

## What it does

- **Public page** — chronological list of upcoming sports events, deadlines, and league links. No login required.
- **Admin panel** — manage families, students, sports, and critical dates via form or CSV upload.
- **Email reminders** — a daily scheduler emails all families N days before each deadline using admin-authored templates. No AI involved; templates are plain text with variable substitution.

## Stack

| Layer | Technology |
|---|---|
| Language | Python 3.12 |
| Framework | Flask + Jinja2 |
| Database | PostgreSQL 16 |
| Auth | Flask-Login + bcrypt |
| Email | smtplib (stdlib) |
| Scheduler | APScheduler (in-process) |
| Frontend | Bootstrap 5 (CDN) |
| Container | Docker + Docker Compose |

---

## Prerequisites

- Docker and Docker Compose

That's it. No local Python installation required.

---

## Setup

**1. Clone and configure**

```bash
cp .env.example .env
```

Edit `.env` and set at minimum:

| Variable | Description |
|---|---|
| `POSTGRES_PASSWORD` | Database password |
| `SECRET_KEY` | Flask session signing key — generate with `python3 -c "import secrets; print(secrets.token_hex(32))"` |
| `SMTP_HOST` | Your SMTP relay hostname |
| `SMTP_FROM` | The From address for outgoing emails |

**2. Build and start**

```bash
docker compose up --build
```

The container will wait for Postgres, apply the database migration, then start the web server on port 8000.

**3. Create the first admin user**

```bash
docker compose exec web python scripts/create_admin.py <username> <email> <password>
```

Example:
```bash
docker compose exec web python scripts/create_admin.py admin admin@school.org 'S3cur3Pass!'
```

**4. Open the app**

| Page | URL |
|---|---|
| Public events listing | http://localhost:8000 |
| Admin login | http://localhost:8000/admin/login |

---

## Configuration reference

All configuration is via environment variables in `.env`.

| Variable | Default | Description |
|---|---|---|
| `POSTGRES_DB` | `sports_portal` | Database name |
| `POSTGRES_USER` | `sports` | Database user |
| `POSTGRES_PASSWORD` | — | **Required.** Database password |
| `SECRET_KEY` | — | **Required in production.** Flask session key |
| `SMTP_HOST` | — | SMTP server hostname. Emails are skipped if blank. |
| `SMTP_PORT` | `587` | SMTP port |
| `SMTP_USE_TLS` | `true` | Enable STARTTLS |
| `SMTP_USER` | — | SMTP auth username (optional) |
| `SMTP_PASSWORD` | — | SMTP auth password (optional) |
| `SMTP_FROM` | — | From address on outgoing emails |
| `SCHEDULER_HOUR` | `7` | Hour (0–23, server local time) the daily email job runs |
| `PERMANENT_SESSION_LIFETIME_HOURS` | `8` | Admin session timeout |
| `PORT` | `8000` | Host port to bind |

---

## CSV upload

All four entities support bulk upload from the admin panel. Upload rules:
- File must be valid UTF-8 CSV.
- All rows are validated before anything is saved — no partial imports.
- On error, the full file is rejected and a row-by-row error table is shown.

### Families
| Column | Required | Notes |
|---|---|---|
| `last_name` | Yes | |
| `email` | Yes | Must be a valid email. Upserts on email (existing record updated). |

### Students
| Column | Required | Notes |
|---|---|---|
| `family_email` | Yes | Must match an existing family email. |
| `first_name` | Yes | |
| `last_name` | Yes | |
| `grade` | Yes | Integer 0–12. Use `0` for Kindergarten. |
| `teacher` | Yes | |

### Sports
| Column | Required | Notes |
|---|---|---|
| `name` | Yes | Upserts on name (existing record updated). |
| `league` | Yes | |
| `league_website` | No | Full URL including `https://`. |

### Critical Sport Dates
| Column | Required | Notes |
|---|---|---|
| `sport_name` | Yes | Must match an existing sport name. |
| `event_name` | Yes | |
| `deadline` | Yes | Format: `YYYY-MM-DD` |
| `event_description` | No | |

---

## Email templates

Templates are plain text with `{variable}` placeholders. Manage them at `/admin/templates`.

**Available variables:**

| Variable | Value |
|---|---|
| `{event_name}` | Name of the event |
| `{event_description}` | Event description (may be empty) |
| `{deadline}` | Formatted deadline, e.g. `May 15, 2026` |
| `{sport_name}` | Name of the sport |
| `{league}` | League name |
| `{league_website}` | League website URL (may be empty) |
| `{family_last_name}` | Family last name |
| `{days_before}` | Number of days before the deadline this email is sent |

**Template resolution order** (most specific wins):

1. **Event** — set for a single specific deadline
2. **Sport** — default for all deadlines in one sport
3. **Global** — fallback for everything

If no template resolves for an event, the scheduler logs a warning and skips that event without sending.

**Example template body:**
```
Hi {family_last_name} family,

This is a reminder that the {sport_name} {event_name} deadline is coming up
on {deadline} — {days_before} days from now.

{event_description}

For more information, visit the league website: {league_website}
```

---

## Reminder intervals

Configure how many days before a deadline emails are sent at `/admin/intervals`. Multiple intervals are supported — for example, adding both `14` and `7` will send two reminder emails per deadline.

A default of 7 days is seeded on first run.

---

## Admin user management

Admin accounts are created exclusively via the CLI — there is no registration UI.

```bash
# Create a new admin
docker compose exec web python scripts/create_admin.py <username> <email> <password>

# Deactivate an admin (blocks login immediately)
docker compose exec db psql -U sports sports_portal \
  -c "UPDATE admin_users SET is_active = false WHERE username = 'someuser';"
```

---

## Running tests

Tests require the app to be running (they use the live database).

```bash
docker compose exec web python -m pytest tests/ -v
```

Tests truncate all tables between runs. Do not run against a production database.

---

## Data persistence

Postgres data is stored in a Docker named volume (`postgres_data`). It survives `docker compose down` but is removed by `docker compose down -v`.

To back up the database:
```bash
docker compose exec db pg_dump -U sports sports_portal > backup.sql
```

To restore:
```bash
docker compose exec -T db psql -U sports sports_portal < backup.sql
```

---

## Deployment notes

The app is stateless — only the Postgres volume needs to be preserved. To deploy on a cloud provider, point `DATABASE_URL` at a managed Postgres instance and run only the `web` service.

```bash
# Production: skip the db service if using a managed database
docker run --env-file .env -p 8000:8000 peabody-sports-portal
```

Set `TZ` in your container environment if you need the scheduler to fire at a specific local time rather than UTC (e.g. `TZ=America/New_York`).
