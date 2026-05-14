#!/bin/sh
set -e

python - <<'PYEOF'
import psycopg2, os, sys, time

url = os.environ["DATABASE_URL"]

for _ in range(30):
    try:
        conn = psycopg2.connect(url)
        conn.close()
        print("Database ready.")
        break
    except psycopg2.OperationalError:
        time.sleep(1)
else:
    print("Database not available after 30 seconds.", file=sys.stderr)
    sys.exit(1)

conn = psycopg2.connect(url)
conn.autocommit = True
with conn.cursor() as cur:
    with open("/app/migrations/001_initial.sql") as f:
        cur.execute(f.read())
conn.close()
print("Migrations applied.")
PYEOF

exec gunicorn "app:create_app()" \
    --bind 0.0.0.0:8000 \
    --workers 2 \
    --threads 2 \
    --timeout 60
