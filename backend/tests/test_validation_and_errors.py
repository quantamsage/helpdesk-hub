"""Input validation, the error format, and what the client is never shown."""
import pytest

from app import repo
from app.config import ConfigError, parse_cors_origins


def assert_error(res, status: int, code: str):
    assert res.status_code == status, res.text
    body = res.json()
    assert set(body) == {"error"}
    assert body["error"]["code"] == code
    assert body["error"]["message"]


@pytest.mark.parametrize("payload, field", [
    ({"title": "Hi", "description": "Long enough description"}, "title"),
    ({"title": "     ", "description": "Long enough description"}, "title"),  # only spaces
    ({"title": "Valid title", "description": "short"}, "description"),
    ({"title": "Valid title", "description": "x" * 5001}, "description"),
    ({"title": "Valid title"}, "description"),
    ({"title": "Valid title", "description": "Long enough description", "status": "resolved"}, "status"),
])
def test_ticket_create_validation(client, make_customer, payload, field):
    res = client.post("/tickets", json=payload, headers=make_customer().headers)
    assert_error(res, 422, "validation_error")
    assert res.json()["error"]["details"][0]["field"] == field


@pytest.mark.parametrize("payload", [
    {"email": "not-an-email", "name": "A", "password": "password123"},
    {"email": "a@example.com", "name": "", "password": "password123"},
    {"email": "a@example.com", "name": "A", "password": "short"},
    {"email": "a@example.com", "name": "A", "password": "x" * 129},
])
def test_register_validation(client, payload):
    assert_error(client.post("/auth/register", json=payload), 422, "validation_error")


def test_validation_errors_never_echo_the_password(client):
    res = client.post("/auth/register", json={"email": "a@example.com", "name": "A", "password": "secret1"})
    assert "secret1" not in res.text


@pytest.mark.parametrize("payload", [{}, {"status": None}, {"status": "closed"}, {"assignee_id": "nope"}])
def test_ticket_update_validation(client, make_customer, make_staff, open_ticket, payload):
    ticket_id = open_ticket(make_customer())["id"]
    res = client.patch(f"/tickets/{ticket_id}", json=payload, headers=make_staff().headers)
    assert_error(res, 422, "validation_error")


@pytest.mark.parametrize("query", ["limit=0", "limit=101", "offset=-1", "status=closed", "assignee=bob", "limit=abc"])
def test_list_query_validation(client, make_staff, query):
    assert_error(client.get(f"/tickets?{query}", headers=make_staff().headers), 422, "validation_error")


def test_bad_ticket_id_in_path(client, make_customer):
    assert_error(client.get("/tickets/123", headers=make_customer().headers), 422, "validation_error")


def test_comment_validation(client, make_customer, open_ticket):
    cara = make_customer()
    ticket_id = open_ticket(cara)["id"]
    for body in ("", "   ", "x" * 2001):
        res = client.post(f"/tickets/{ticket_id}/comments", json={"body": body}, headers=cara.headers)
        assert_error(res, 422, "validation_error")


def test_invalid_json_body(client):
    res = client.post("/auth/login", content="{not json", headers={"Content-Type": "application/json"})
    assert_error(res, 422, "validation_error")
    assert res.json()["error"]["details"][0]["field"] == "body"


def test_unknown_route_and_wrong_method(client):
    assert_error(client.get("/nope"), 404, "not_found")
    assert_error(client.delete("/tickets"), 405, "method_not_allowed")


def test_unexpected_error_is_generic_and_logged(client, make_customer, monkeypatch, caplog):
    cara = make_customer()

    def broken(*args, **kwargs):
        raise RuntimeError('relation "support_secret" at /srv/app/repo.py line 42')

    monkeypatch.setattr(repo, "list_tickets", broken)
    res = client.get("/tickets", headers=cara.headers)

    assert_error(res, 500, "internal_error")
    assert "support_secret" not in res.text and "repo.py" not in res.text
    assert "support_secret" in caplog.text  # full details are in the server log
    assert res.headers["X-Content-Type-Options"] == "nosniff"  # headers still applied


def test_failed_request_saves_nothing(client, make_customer, open_ticket, monkeypatch, admin_conn):
    """If anything fails after the comment INSERT, the whole request rolls back."""
    cara = make_customer()
    ticket_id = open_ticket(cara)["id"]

    def broken(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(repo, "touch_ticket", broken)
    res = client.post(f"/tickets/{ticket_id}/comments", json={"body": "half-saved?"}, headers=cara.headers)
    assert res.status_code == 500
    assert admin_conn.execute("SELECT count(*) FROM support_comments").fetchone()[0] == 0


# ---- Security headers and CORS ---------------------------------------------

def test_security_headers(client):
    headers = client.get("/health").headers
    assert headers["X-Content-Type-Options"] == "nosniff"
    assert headers["X-Frame-Options"] == "DENY"
    assert headers["Referrer-Policy"] == "no-referrer"
    assert "frame-ancestors 'none'" in headers["Content-Security-Policy"]
    assert "Strict-Transport-Security" not in headers  # only in production


def test_hsts_and_no_docs_in_production(settings):
    from dataclasses import replace

    from fastapi.testclient import TestClient

    from app.main import create_app

    with TestClient(create_app(replace(settings, environment="production"))) as prod:
        assert "max-age" in prod.get("/health").headers["Strict-Transport-Security"]
        assert prod.get("/docs").status_code == 404


def test_cors_allows_only_configured_origin(client):
    allowed = client.get("/health", headers={"Origin": "http://localhost:3000"})
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"

    blocked = client.get("/health", headers={"Origin": "https://evil.example"})
    assert "access-control-allow-origin" not in blocked.headers


def test_cors_preflight(client):
    res = client.options("/tickets", headers={
        "Origin": "http://localhost:3000",
        "Access-Control-Request-Method": "POST",
        "Access-Control-Request-Headers": "authorization,content-type",
    })
    assert res.status_code == 200


def test_cors_wildcard_is_refused():
    with pytest.raises(ConfigError):
        parse_cors_origins("https://a.com,*")
    assert parse_cors_origins(" https://a.com/ , http://localhost:3000") == ["https://a.com", "http://localhost:3000"]
