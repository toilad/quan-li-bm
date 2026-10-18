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



def test_a_login_on_this_machine_lasts_30_days_7_idle_and_anything_else_keeps_24h_7_days():
    from datetime import timedelta

    from wg_core import auth
    from wg_core.auth import AuthSession
    from wg_core.db import session_scope

    with session_scope() as s:
        if not auth.users_exist(s):
            auth.create_user(s, "owner2", "a-long-password-123")
        user = s.query(auth.User).first()
        name = user.username
    pw = "a-long-password-123"
    with session_scope() as s:
        local = auth.login(s, name, pw, "127.0.0.1", local=True)
        remote = auth.login(s, name, pw, "203.0.113.5")
        if local is None:  # the suite's owner may have another password: set one for this test
            auth.set_password(s, s.query(auth.User).filter_by(username=name).one(), pw)
    if local is None:
        with session_scope() as s:
            local = auth.login(s, name, pw, "127.0.0.1", local=True)
            remote = auth.login(s, name, pw, "203.0.113.5")

    def age(token, idle_days, total_days):
        with session_scope() as s:
            row = s.query(AuthSession).filter_by(token_hash=auth._token_hash(token)).one()
            row.last_seen = auth._now() - timedelta(days=idle_days)
            row.created_at = auth._now() - timedelta(days=total_days)
        with session_scope() as s:
            return auth.session_user(s, token) is not None

    assert age(local, 3, 20)          # 3 days idle, 20 days old: still in
    assert not age(remote, 2, 2)      # elsewhere: 24 h idle ends it
    with session_scope() as s:
        local2 = auth.login(s, name, pw, "127.0.0.1", local=True)
    assert not age(local2, 1, 31)     # never past 30 days
    with session_scope() as s:
        local3 = auth.login(s, name, pw, "127.0.0.1", local=True)
    assert not age(local3, 8, 8)      # 7 days idle ends it


def test_a_proxied_request_is_never_treated_as_local(client):
    from app.auth_api import _local

    class R:
        def __init__(self, headers):
            self.client = type("C", (), {"host": "127.0.0.1"})()
            self.headers = headers

    assert _local(R({})) and not _local(R({"x-forwarded-for": "198.51.100.7"})) and not _local(R({"forwarded": "for=198.51.100.7"}))
