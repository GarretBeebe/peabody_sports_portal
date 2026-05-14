-- Idempotent: safe to re-run on every container start

CREATE TABLE IF NOT EXISTS family (
    id          SERIAL PRIMARY KEY,
    last_name   VARCHAR(100) NOT NULL,
    email       VARCHAR(254) NOT NULL UNIQUE,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS student (
    id          SERIAL PRIMARY KEY,
    family_id   INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
    first_name  VARCHAR(100) NOT NULL,
    last_name   VARCHAR(100) NOT NULL,
    grade       SMALLINT NOT NULL CHECK (grade BETWEEN 0 AND 12),
    teacher     VARCHAR(100) NOT NULL,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_student_family_id ON student(family_id);

CREATE TABLE IF NOT EXISTS sport (
    id              SERIAL PRIMARY KEY,
    name            VARCHAR(100) NOT NULL UNIQUE,
    league          VARCHAR(100)  NOT NULL,
    league_website  VARCHAR(2048),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS critical_sport_dates (
    id                  SERIAL PRIMARY KEY,
    sport_id            INTEGER NOT NULL REFERENCES sport(id) ON DELETE CASCADE,
    event_name          VARCHAR(200) NOT NULL,
    event_description   TEXT,
    deadline            DATE NOT NULL,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_csd_sport_id ON critical_sport_dates(sport_id);
CREATE INDEX IF NOT EXISTS idx_csd_deadline  ON critical_sport_dates(deadline);

CREATE TABLE IF NOT EXISTS admin_users (
    id              SERIAL PRIMARY KEY,
    username        VARCHAR(100) NOT NULL UNIQUE,
    email           VARCHAR(254) NOT NULL UNIQUE,
    password_hash   VARCHAR(128) NOT NULL,
    is_active       BOOLEAN NOT NULL DEFAULT TRUE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    last_login_at   TIMESTAMPTZ
);

CREATE TABLE IF NOT EXISTS reminder_intervals (
    id          SERIAL PRIMARY KEY,
    days_before INTEGER NOT NULL UNIQUE CHECK (days_before > 0)
);

-- Seed a sensible default on first run
INSERT INTO reminder_intervals (days_before)
SELECT 7
WHERE NOT EXISTS (SELECT 1 FROM reminder_intervals);

-- Template resolution order (most specific wins):
--   event  → overrides everything for one specific deadline
--   sport  → default for all deadlines in that sport
--   global → catch-all fallback
--
-- Supported variables: {event_name} {event_description} {deadline}
--   {sport_name} {league} {league_website} {family_last_name} {days_before}
CREATE TABLE IF NOT EXISTS email_templates (
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

-- Deduplication log — ON CONFLICT DO NOTHING prevents re-sends on restart
CREATE TABLE IF NOT EXISTS notification_log (
    id              SERIAL PRIMARY KEY,
    family_id       INTEGER NOT NULL REFERENCES family(id) ON DELETE CASCADE,
    sport_date_id   INTEGER NOT NULL REFERENCES critical_sport_dates(id) ON DELETE CASCADE,
    days_before     INTEGER NOT NULL,
    sent_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    recipient_email VARCHAR(254) NOT NULL,
    subject         VARCHAR(200) NOT NULL,
    status          VARCHAR(10)  NOT NULL CHECK (status IN ('sent', 'failed')),
    error_message   TEXT,
    CONSTRAINT uq_notification UNIQUE (family_id, sport_date_id, days_before)
);

CREATE INDEX IF NOT EXISTS idx_notif_sport_date_id ON notification_log(sport_date_id);
CREATE INDEX IF NOT EXISTS idx_notif_family_id     ON notification_log(family_id);
