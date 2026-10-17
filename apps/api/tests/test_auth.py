"""Login protects every /api route except health and the login endpoints."""
from fastapi.testclient import TestClient
from sqlalchemy import select

from tests.conftest import TEST_PASSWORD, TEST_USER
from wg_core import auth
from wg_core.db import session_scope


def _anon():
    from app.main import app

    return TestClient(app)


def test_every_api_route_needs_a_session_except_health_and_login():
    with _anon() as c:
        assert c.get("/api/health").status_code == 200
        st = c.get("/api/auth/status").json()
        assert st == {"authenticated": False, "user": None, "setup_needed": True, "setup_allowed": True}
        for method, path in [("get", "/api/status"), ("get", "/api/settings"), ("get", "/api/pdf"), ("get", "/api/domains/roots"),
                             ("post", "/api/domains/run"), ("put", "/api/domains/dns-write"), ("get", "/api/jobs"),
                             ("get", "/api/google/oauth/start"), ("get", "/api/websites/preview")]:
            r = getattr(c, method)(path)
            assert r.status_code == 401 and r.json()["status"] == "unauthenticated", path


def test_first_account_from_this_machine_then_login_logout(client):
    with _anon() as c:
        # an account already exists (the client fixture made one) → setup refused
        assert c.post("/api/auth/setup", json={"username": "x", "password": "long-enough-pass"}).status_code == 409
        assert c.post("/api/auth/login", json={"username": TEST_USER, "password": "wrong-password"}).status_code == 401
        r = c.post("/api/auth/login", json={"username": TEST_USER.upper(), "password": TEST_PASSWORD})
        assert r.status_code == 200
        cookie = r.headers["set-cookie"].lower()
        assert "httponly" in cookie and "samesite=lax" in cookie
        assert c.get("/api/status").status_code == 200
        c.post("/api/auth/logout")
        assert c.get("/api/status").status_code == 401
    with session_scope() as s:  # only a hash of the token and of the password are stored
        u = s.scalar(select(auth.User))
        assert u.pw_hash.startswith("scrypt$") and TEST_PASSWORD not in u.pw_hash


def test_setup_only_without_accounts_and_only_locally():
    with _anon() as c:
        assert c.post("/api/auth/setup", json={"username": "owner", "password": "short"}).status_code == 422
        assert c.post("/api/auth/setup", json={"username": "owner", "password": "a-long-password"},
                      headers={"X-Forwarded-For": "203.0.113.9"}).status_code == 403  # through a proxy = not local
        r = c.post("/api/auth/setup", json={"username": "Owner", "password": "a-long-password"})
        assert r.status_code == 200 and c.get("/api/auth/status").json()["user"] == "owner"
        assert c.post("/api/auth/setup", json={"username": "two", "password": "a-long-password"}).status_code == 409


def test_failed_logins_are_throttled(monkeypatch):
    monkeypatch.setattr(auth, "throttle", auth.Throttle(limit=3, window=60))
    import app.auth_api as api

    monkeypatch.setattr(api.auth, "throttle", auth.throttle)
    with session_scope() as s:
        auth.create_user(s, "owner", "a-long-password")
    with _anon() as c:
        for _ in range(3):
            assert c.post("/api/auth/login", json={"username": "owner", "password": "nope-nope-nope"}).status_code == 401
        assert c.post("/api/auth/login", json={"username": "owner", "password": "a-long-password"}).status_code == 429


def test_foreign_origin_cannot_change_anything(client):
    r = client.put("/api/domains/dns-write", json={"enabled": False}, headers={"Origin": "https://evil.example"})
    assert r.status_code == 403
    assert client.put("/api/domains/dns-write", json={"enabled": False}, headers={"Origin": "http://localhost:3210"}).status_code == 200


def test_password_change_ends_other_sessions(client):
    with _anon() as other:
        assert other.post("/api/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD}).status_code == 200
        assert client.post("/api/auth/password", json={"current": TEST_PASSWORD, "new": "short"}).status_code == 422
        assert client.post("/api/auth/password", json={"current": TEST_PASSWORD, "new": "another-long-pass"}).status_code == 200
        assert client.get("/api/status").status_code == 200  # this browser got a new session
        assert other.get("/api/status").status_code == 401  # the other one was logged out
