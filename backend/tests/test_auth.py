from datetime import datetime, timedelta, timezone

import jwt


def test_register_creates_customer_and_never_returns_password(client):
    res = client.post("/auth/register", json={"email": "Ann@Example.com", "name": " Ann ", "password": "password123"})
    assert res.status_code == 201
    body = res.json()
    assert body["role"] == "customer"
    assert body["email"] == "ann@example.com"  # stored lowercase
    assert body["name"] == "Ann"  # trimmed
    assert "password" not in str(body)


def test_cannot_register_as_staff(client):
    res = client.post("/auth/register", json={"email": "e@example.com", "name": "Eve", "password": "password123", "role": "staff"})
    assert res.status_code == 422
    assert res.json()["error"]["details"][0]["field"] == "role"


def test_duplicate_email_is_rejected_case_insensitively(client, make_customer):
    make_customer("cara@example.com")
    res = client.post("/auth/register", json={"email": "CARA@example.com", "name": "C", "password": "password123"})
    assert res.status_code == 409
    assert res.json()["error"]["code"] == "conflict"


def test_login_and_me(client, make_customer):
    cara = make_customer()
    res = client.get("/auth/me", headers=cara.headers)
    assert res.status_code == 200
    assert res.json()["email"] == "cara@example.com"


def test_wrong_password_and_unknown_email_get_the_same_error(client, make_customer):
    make_customer()
    wrong = client.post("/auth/login", json={"email": "cara@example.com", "password": "nope-nope"})
    unknown = client.post("/auth/login", json={"email": "ghost@example.com", "password": "nope-nope"})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()


def test_password_is_hashed_with_argon2(admin_conn, make_customer):
    make_customer()
    stored = admin_conn.execute("SELECT password_hash FROM support_users").fetchone()[0]
    assert stored.startswith("$argon2id$")


def test_missing_token_is_401(client):
    res = client.get("/auth/me")
    assert res.status_code == 401
    assert res.json()["error"]["code"] == "unauthorized"


def test_garbage_and_wrong_scheme_tokens_are_401(client):
    assert client.get("/auth/me", headers={"Authorization": "Bearer not-a-jwt"}).status_code == 401
    assert client.get("/auth/me", headers={"Authorization": "Basic abc"}).status_code == 401


def test_expired_token_is_401(client, settings, make_customer):
    cara = make_customer()
    past = datetime.now(timezone.utc) - timedelta(minutes=5)
    token = jwt.encode({"sub": cara.id, "exp": past}, settings.jwt_secret, algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_token_signed_with_another_secret_is_401(client, make_customer):
    cara = make_customer()
    future = datetime.now(timezone.utc) + timedelta(minutes=5)
    token = jwt.encode({"sub": cara.id, "exp": future}, "an-attacker-secret-that-is-32-chars-long", algorithm="HS256")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_unsigned_alg_none_token_is_401(client, make_customer):
    cara = make_customer()
    token = jwt.encode({"sub": cara.id, "exp": 9999999999}, key=None, algorithm="none")
    assert client.get("/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 401


def test_create_staff_script_makes_a_staff_user(client, make_staff):
    sam = make_staff()
    assert client.get("/auth/me", headers=sam.headers).json()["role"] == "staff"
