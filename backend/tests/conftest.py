"""Test setup. Tests run against a REAL PostgreSQL database (not mocks).

Needs two connection strings in backend/.env (see .env.example):
- TEST_DATABASE_URL:       the restricted support_app role (what the app uses)
- TEST_ADMIN_DATABASE_URL: the owner, used to reset tables and create staff

Safety: tables are wiped before every test, so the database name must
contain "test". This stops the tests ever running against a real database.
"""
import os
from dataclasses import dataclass
from pathlib import Path

import psycopg
import pytest
from dotenv import load_dotenv
from fastapi.testclient import TestClient
from psycopg.conninfo import conninfo_to_dict

from app.config import Settings
from app.main import create_app
from create_staff import create_staff

load_dotenv()
SCHEMA_FILE = Path(__file__).resolve().parents[2] / "db" / "schema.sql"
PASSWORD = "correct-horse-battery"


def _test_url(name: str) -> str:
    url = os.getenv(name, "").strip()
    if not url:
        pytest.exit(f"{name} is not set. See backend/.env.example.", returncode=2)
    if "test" not in (conninfo_to_dict(url).get("dbname") or ""):
        pytest.exit(f"Refusing to run: the database in {name} must have 'test' in its name.", returncode=2)
    return url


@pytest.fixture(scope="session")
def admin_conn():
    with psycopg.connect(_test_url("TEST_ADMIN_DATABASE_URL"), autocommit=True) as conn:
        tables_exist = conn.execute("SELECT to_regclass('support_users') IS NOT NULL").fetchone()[0]
        if not tables_exist:
            conn.execute(SCHEMA_FILE.read_text())
        yield conn


@pytest.fixture(scope="session")
def settings() -> Settings:
    return Settings(
        database_url=_test_url("TEST_DATABASE_URL"),
        jwt_secret="test-only-secret-that-is-at-least-32-characters",
        access_token_minutes=30,
        cors_origins=["http://localhost:3000"],
        environment="development",
    )


@pytest.fixture(scope="session")
def client(settings, admin_conn):
    # raise_server_exceptions=False: see the 500 response a real client would get
    with TestClient(create_app(settings), raise_server_exceptions=False) as c:
        yield c


@pytest.fixture(autouse=True)
def clean_tables(admin_conn):
    admin_conn.execute("TRUNCATE support_comments, support_tickets, support_users CASCADE")


@dataclass
class Account:
    id: str
    email: str
    headers: dict


def _login(client, email: str) -> dict:
    res = client.post("/auth/login", json={"email": email, "password": PASSWORD})
    assert res.status_code == 200, res.text
    return {"Authorization": f"Bearer {res.json()['access_token']}"}


@pytest.fixture
def make_customer(client):
    def make(email: str = "cara@example.com", name: str = "Cara") -> Account:
        res = client.post("/auth/register", json={"email": email, "name": name, "password": PASSWORD})
        assert res.status_code == 201, res.text
        return Account(res.json()["id"], email, _login(client, email))
    return make


@pytest.fixture
def make_staff(client, admin_conn):
    def make(email: str = "sam@example.com", name: str = "Sam") -> Account:
        user = create_staff(admin_conn, email, name, PASSWORD)
        return Account(str(user["id"]), email, _login(client, email))
    return make


@pytest.fixture
def open_ticket(client):
    def make(account: Account, title: str = "Cannot log in", description: str = "Login fails since this morning.") -> dict:
        res = client.post("/tickets", json={"title": title, "description": description}, headers=account.headers)
        assert res.status_code == 201, res.text
        return res.json()
    return make
