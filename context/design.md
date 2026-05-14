# Peabody Sports Portal — System Design

## Tech Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.12 | Strong ecosystem for web + email + scheduling |
| Framework | Flask + Jinja2 | Server-rendered, no JS framework needed for CRUD admin |
| Database | PostgreSQL 16 | Real relational structure; safe concurrent access in Docker |
| Auth | Flask-Login + bcrypt | Session-based, standard, no over-engineering |
| Email | smtplib (stdlib) | No SaaS lock-in; works with any SMTP relay via env vars |
| Scheduler | APScheduler (in-process) | One daily job — no Celery/Redis/second container needed |
| Frontend | Bootstrap 5 (CDN) + Jinja2 | Plain HTML, no React |

---

## Data Models

```sql
-- FAMILIES
CREATE TABLE family (
    id          SERIAL PRIMARY KEY,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(254) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- STUDENTS
CREATE TABLE student (
    id          SERIAL PRIMARY KEY,
    family_id   INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    grade       SMALLINT NOT NULL CHECK (grade BETWEEN 0 AND 12),  -- 0 = Kindergarten
    teacher     VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_student_family_id ON student(family_id);

-- SPORTS
CREATE TABLE sport (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    league          VARCHAR(100) NOT NULL,
    league_website  VARCHAR(2048),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- CRITICAL SPORT DATES
CREATE TABLE critical_sport_dates (
    id                  SERIAL PRIMARY KEY,
    sport_id            INTEGER NOT NULL REFERENCES sport(id) ON DELETE CASCADE,
    event_name          VARCHAR(200) NOT NULL,
    event_description   TEXT,
    deadline            DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
CREATE INDEX idx_csd_sport_id ON critical_sport_dates(sport_id);
CREATE INDEX idx_csd_deadline ON critical_sport_dates(deadline);

-- ADMIN USERS (no self-registration; created via CLI only)
CREATE TABLE admin_users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL UNIQUE,
    password_hash   VARCHAR(128) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

-- REMINDER INTERVALS (multiple allowed — e.g. 14, 7, 1 days before)
CREATE TABLE reminder_intervals (
    id          SERIAL PRIMARY KEY,
    days_before INTEGER NOT NULL UNIQUE CHECK (days_before > 0)
);
-- Default seed: INSERT INTO reminder_intervals (days_before) VALUES (7);

-- EMAIL TEMPLATES (3-tier resolution: event > sport > global)
-- Supported template variables:
--   {event_name} {event_description} {deadline} {sport_name}
--   {league} {league_website} {family_last_name} {days_before}
CREATE TABLE email_templates (
    id              SERIAL PRIMARY KEY,
    scope           VARCHAR(10) NOT NULL CHECK (scope IN ('global', 'sport', 'event')),
    sport_id        INTEGER REFERENCES sport(id) ON DELETE CASCADE,
    sport_date_id   INTEGER REFERENCES critical_sport_dates(id) ON DELETE CASCADE,
    subject         VARCHAR(200) NOT NULL,
    body_text       TEXT NOT NULL,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    CONSTRAINT chk_template_scope CHECK (
        (scope = 'global' AND sport_id IS NULL     AND sport_date_id IS NULL) OR
        (scope = 'sport'  AND sport_id IS NOT NULL AND sport_date_id IS NULL) OR
        (scope = 'event'  AND sport_date_id IS NOT NULL)
    ),
    CONSTRAINT uq_template_target UNIQUE NULLS NOT DISTINCT (scope, sport_id, sport_date_id)
);

-- NOTIFICATION LOG (deduplication; prevents re-sends on container restart)
CREATE TABLE notification_log (
    id              SERIAL PRIMARY KEY,
    family_id       INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
    sport_date_id   INTEGER NOT NULL REFERENCES critical_sport_dates(id) ON DELETE CASCADE,
    days_before     INTEGER NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recipient_email VARCHAR(254) NOT NULL,
    subject         VARCHAR(200) NOT NULL,
    status          VARCHAR(10) NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message   TEXT,
    CONSTRAINT uq_notification UNIQUE (family_id, sport_date_id, days_before)
);
CREATE INDEX idx_notif_sport_date_id ON notification_log(sport_date_id);
CREATE INDEX idx_notif_family_id ON notification_log(family_id);
```

---

## Application Structure

```
peabody_sports_portal/
├── app/
│   ├── __init__.py          # create_app() factory
│   ├── extensions.py        # db pool, Flask-Login, bcrypt instances (avoids circular imports)
│   ├── db.py                # get_db() context manager (psycopg2 ThreadedConnectionPool)
│   ├── auth/
│   │   ├── routes.py        # GET/POST /admin/login, GET /admin/logout
│   │   └── forms.py         # LoginForm (Flask-WTF + CSRF)
│   ├── admin/
│   │   ├── routes.py        # All /admin/* CRUD + upload routes
│   │   ├── forms.py         # WTForms per entity
│   │   └── csv_import.py    # CSV parse + validate (no HTTP — unit-testable)
│   ├── public/
│   │   └── routes.py        # GET / — unauthenticated listing
│   ├── email/
│   │   ├── scheduler.py     # APScheduler init, daily job registration
│   │   ├── sender.py        # SMTP send_email()
│   │   └── pipeline.py      # resolve_template(), substitute_vars(), run_daily_job()
│   └── templates/
│       ├── base.html
│       ├── public/
│       │   └── index.html
│       └── admin/
│           ├── login.html
│           ├── dashboard.html
│           ├── families/      # list, create, edit, upload
│           ├── students/
│           ├── sports/
│           ├── sport_dates/
│           ├── templates/    # email template management
│           └── intervals/    # reminder interval configuration
├── migrations/
│   └── 001_initial.sql      # CREATE TABLE IF NOT EXISTS — safe to re-run
├── scripts/
│   └── create_admin.py      # CLI: python scripts/create_admin.py <user> <email> <pass>
├── tests/
│   ├── conftest.py
│   ├── test_email_pipeline.py
│   ├── test_csv_import.py
│   └── test_public_routes.py
├── docker-compose.yml
├── Dockerfile
├── entrypoint.sh            # run migrations → start gunicorn
└── .env.example
```

---

## Auth Flow

- **Login**: `POST /admin/login` validates CSRF token + bcrypt hash → signed session cookie
- **Protected routes**: `@login_required` on all `/admin/*` routes; redirects unauthenticated requests to `/admin/login?next=<url>`
- **Session config**: `HttpOnly`, `SameSite=Lax`, 8-hour lifetime (configurable via `PERMANENT_SESSION_LIFETIME_HOURS`)
- **Bootstrap**: no registration UI — run `docker compose exec web python scripts/create_admin.py` to seed first admin
- **Secret key**: `SECRET_KEY` env var (32+ random bytes); never baked into image

---

## Email Pipeline

The scheduler fires once daily at `SCHEDULER_HOUR` (default 7 AM):

```
for each row in reminder_intervals (e.g. days_before = 14, 7, 1):
    target_date = today + timedelta(days=days_before)

    events = SELECT csd.*, s.name, s.league, s.league_website
             FROM critical_sport_dates csd
             JOIN sport s ON s.id = csd.sport_id
             WHERE csd.deadline = target_date

    for each event:
        template = resolve_template(event.id, event.sport_id)
            1. Try scope='event',  sport_date_id = event.id
            2. Try scope='sport',  sport_id = event.sport_id
            3. Try scope='global'
            → if none found: log warning, skip event

        families = SELECT * FROM family   (all families; broadcast to all)

        for each family:
            INSERT INTO notification_log (family_id, sport_date_id, days_before, ...)
            ON CONFLICT (family_id, sport_date_id, days_before) DO NOTHING RETURNING id
            → if no row returned: already sent, skip

            subject = substitute_vars(template.subject, event, family, days_before)
            body    = substitute_vars(template.body_text, event, family, days_before)

            try:
                send_email(family.email, subject, body)
                UPDATE notification_log SET status='sent'
            except SMTPException:
                UPDATE notification_log SET status='failed', error_message=...
```

**SMTP env vars**: `SMTP_HOST`, `SMTP_PORT` (587), `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`, `SMTP_USE_TLS` (true).

**Template variables** (substituted via `str.format_map`):
- `{event_name}`, `{event_description}`, `{deadline}`, `{sport_name}`
- `{league}`, `{league_website}`, `{family_last_name}`, `{days_before}`

Unknown `{placeholders}` raise a `KeyError` — they do not silently pass through.

---

## CSV Upload

FK columns use natural keys (not numeric IDs) to make CSVs human-editable:

| Entity | Required columns | Optional | FK lookup |
|---|---|---|---|
| family | `last_name`, `email` | — | — |
| student | `family_email`, `first_name`, `last_name`, `grade`, `teacher` | — | `family_email` → family |
| sport | `name`, `league` | `league_website` | — |
| critical_sport_dates | `sport_name`, `event_name`, `deadline` (YYYY-MM-DD) | `event_description` | `sport_name` → sport |

**Error behavior**: all-or-nothing. All rows validated before any are committed. On any error, full rollback; admin sees a table of row numbers + error messages.

**Upsert behavior**:
- `family`: upsert on `email`
- `sport`: upsert on `name`
- `student`, `critical_sport_dates`: insert only; duplicates are rejected with a clear error

---

## Public Portal Page

`GET /` — no auth required.

```sql
SELECT csd.event_name, csd.event_description, csd.deadline,
       s.name AS sport_name, s.league_website
FROM critical_sport_dates csd
JOIN sport s ON s.id = csd.sport_id
WHERE csd.deadline >= CURRENT_DATE
ORDER BY csd.deadline ASC;
```

Shows: sport name, event name, deadline, event description, league website link (if set). Past deadlines are hidden. No login prompt.

---

## Docker Compose

```yaml
services:
  db:
    image: postgres:16-alpine
    restart: unless-stopped
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-sports_portal}
      POSTGRES_USER: ${POSTGRES_USER:-sports}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-sports}"]
      interval: 5s
      timeout: 5s
      retries: 5

  web:
    build: .
    restart: unless-stopped
    depends_on:
      db: { condition: service_healthy }
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-sports}:${POSTGRES_PASSWORD}@db:5432/${POSTGRES_DB:-sports_portal}
      SECRET_KEY: ${SECRET_KEY}
      SMTP_HOST: ${SMTP_HOST}
      SMTP_PORT: ${SMTP_PORT:-587}
      SMTP_USER: ${SMTP_USER:-}
      SMTP_PASSWORD: ${SMTP_PASSWORD:-}
      SMTP_FROM: ${SMTP_FROM}
      SMTP_USE_TLS: ${SMTP_USE_TLS:-true}
      SCHEDULER_HOUR: ${SCHEDULER_HOUR:-7}
      PERMANENT_SESSION_LIFETIME_HOURS: ${PERMANENT_SESSION_LIFETIME_HOURS:-8}
    ports:
      - "${PORT:-8000}:8000"
    entrypoint: ["/app/entrypoint.sh"]

volumes:
  postgres_data:
```

**Dockerfile**:
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN chmod +x entrypoint.sh
EXPOSE 8000
```

**entrypoint.sh**: wait for DB health → run `migrations/001_initial.sql` → start gunicorn.
Migrations use `CREATE TABLE IF NOT EXISTS` throughout — safe to re-run on every restart.

---

## Confirmed Decisions

| Gap | Decision |
|---|---|
| Email recipients | All families for all sports (broadcast). No enrollment table. |
| Template scope | 3-tier: global → sport → event. Most specific wins. |
| Reminder intervals | Multiple (configurable via `reminder_intervals` table). Default seed: 7 days. |
| No template found | Scheduler logs warning, skips event. Never sends blank email. |
| CSV error handling | All-or-nothing. Full rollback on any row error. |
| CSV upsert | family + sport upsert on natural key; student + sport_dates insert-only. |
| Grade format | SMALLINT, 0 = Kindergarten. Admin UI renders 0 as "K". |
| Admin roles | All admins have full access. No RBAC. |
| Past deadlines (public) | Hidden. Admin can still view/edit in admin UI. |
| Email format | Plain text only. |
| Admin account creation | CLI only (`scripts/create_admin.py`). No registration UI. |
| Scheduler timezone | Server local time (set `TZ` env var in Docker if needed). |
