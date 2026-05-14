#!/usr/bin/env python
"""Create an admin user. Run inside the container:

    docker compose exec web python scripts/create_admin.py <username> <email> <password>
"""
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    if len(sys.argv) != 4:
        print("Usage: python scripts/create_admin.py <username> <email> <password>")
        sys.exit(1)

    username, email, password = sys.argv[1], sys.argv[2], sys.argv[3]

    from app import create_app
    from app.db import get_db
    from app.extensions import bcrypt

    app = create_app()
    with app.app_context():
        password_hash = bcrypt.generate_password_hash(password).decode("utf-8")
        try:
            with get_db() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "INSERT INTO admin_users (username, email, password_hash) "
                        "VALUES (%s, %s, %s)",
                        (username, email, password_hash),
                    )
            print(f"Admin user '{username}' created.")
        except Exception as exc:
            if "unique" in str(exc).lower():
                print("Error: username or email already exists.")
            else:
                print(f"Error: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    main()
