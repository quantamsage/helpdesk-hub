"""Create a staff account. Run by the owner, locally, never deployed.

    python create_staff.py --email anna@example.com --name "Anna"

Uses ADMIN_DATABASE_URL (the database owner), because the app's own database
role is deliberately NOT allowed to create staff accounts.
"""
import argparse
import getpass
import os
import sys

import psycopg
from dotenv import load_dotenv
from psycopg.errors import UniqueViolation
from psycopg.rows import dict_row
from pydantic import ValidationError

from app.schemas import RegisterRequest
from app.security import hash_password


def create_staff(conn: psycopg.Connection, email: str, name: str, password: str) -> dict:
    """Validates with the same rules as registration, then inserts a staff user."""
    details = RegisterRequest(email=email, name=name, password=password)
    with conn.cursor(row_factory=dict_row) as cur:
        cur.execute(
            """INSERT INTO support_users (email, name, password_hash, role)
               VALUES (%(email)s, %(name)s, %(password_hash)s, 'staff')
               RETURNING id, email, name, role""",
            {"email": details.email, "name": details.name, "password_hash": hash_password(details.password)},
        )
        return cur.fetchone()


def main() -> int:
    load_dotenv()
    parser = argparse.ArgumentParser(description="Create a staff account.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--name", required=True)
    args = parser.parse_args()

    admin_url = os.getenv("ADMIN_DATABASE_URL", "").strip()
    if not admin_url:
        print("Set ADMIN_DATABASE_URL in backend/.env first (the owner connection string).")
        return 1

    password = getpass.getpass("Password for the new staff account (min 8 characters): ")
    if password != getpass.getpass("Repeat password: "):
        print("Passwords don't match.")
        return 1

    try:
        with psycopg.connect(admin_url) as conn:  # commits when the block ends
            user = create_staff(conn, args.email, args.name, password)
    except ValidationError as exc:
        for err in exc.errors():
            print(f"Invalid {err['loc'][0]}: {err['msg']}")
        return 1
    except UniqueViolation:
        print("An account with this email already exists.")
        return 1
    except psycopg.OperationalError:
        print("Couldn't connect to the database. Check ADMIN_DATABASE_URL.")
        return 1

    print(f"Created staff account: {user['name']} <{user['email']}>")
    return 0


if __name__ == "__main__":
    sys.exit(main())
