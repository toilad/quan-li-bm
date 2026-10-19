"""Test setup: separate database `qlbm_test` on the embedded PostgreSQL, fake credentials, every external
HTTP call mocked with respx (Google, iNET, cPanel, Anthropic, DNS-over-HTTPS). No real account is touched."""
import json
import os
import sys
from pathlib import Path

import pytest
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
FIXTURES = ROOT.parents[1] / "test-fixtures" / "pdf"


def _fake_service_account(tmp: Path) -> Path:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pem = key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
    p = tmp / "sa.json"
    p.write_text(json.dumps({"client_email": "test@test.iam.gserviceaccount.com", "private_key": pem}), encoding="utf-8")
    return p


@pytest.fixture(scope="session", autouse=True)
def _env(tmp_path_factory):
    tmp = tmp_path_factory.mktemp("qlbm")
    import pgserver

    srv = pgserver.get_server(str(ROOT / ".pgdata"), cleanup_mode=None)
    if "qlbm_test" not in srv.psql("SELECT datname FROM pg_database WHERE datname='qlbm_test';"):
        srv.psql("CREATE DATABASE qlbm_test;")
    os.environ.update({
        "DATABASE_URL": srv.get_uri("qlbm_test"),
        "DATA_DIR": str(tmp / "data"),
        "GOOGLE_SERVICE_ACCOUNT_FILE": str(_fake_service_account(tmp)),
        "SHEET_ID": "TESTSHEET", "SHEET_TAB": "Phoi US", "DRIVE_FOLDER_ID": "TESTFOLDER",
        "ANTHROPIC_API_KEY": "test-key",
        "CPANEL_USER_N1": "u1", "CPANEL_TOKEN_N1": "t1", "INET_API_KEY_N1": "k1",
    })
    from wg_core import registry

    registry.setup()
    yield


@pytest.fixture(autouse=True)
def clean_db(_env):
    from sqlalchemy import text

    from wg_core.db import engine
    from wg_core.integrations import google

    google._token_cache.clear()
    from wg_core.integrations import net

    net.system_resolve = lambda name: []  # never a real DNS lookup in tests
    net.cert_valid = lambda domain: (True, "chứng chỉ hợp lệ (test)")  # never a real TLS connection in tests
    from wg_core import runtime_config

    runtime_config._cache.clear()
    with engine().begin() as c:
        c.execute(text("TRUNCATE job_logs, sheet_writes, jobs, pdf_documents, site_choices, app_settings, stored_settings, auth_sessions, users RESTART IDENTITY CASCADE"))
        c.execute(text("UPDATE root_domains SET selected = false"))
    yield


def drain(max_jobs=50):
    """Run queued jobs that are due now (like the worker), return how many ran."""
    from wg_core import jobs

    n = 0
    while n < max_jobs and jobs.run_one():
        n += 1
    return n


TEST_USER, TEST_PASSWORD = "owner", "test-only-pass-123"  # throwaway account inside the test database


@pytest.fixture
def client():
    """API client logged in as the owner (every /api route needs a session)."""
    from fastapi.testclient import TestClient

    from app.main import app
    from wg_core import auth
    from wg_core.db import session_scope

    with session_scope() as s:
        auth.create_user(s, TEST_USER, TEST_PASSWORD)
    with TestClient(app, follow_redirects=False) as c:
        assert c.post("/api/auth/login", json={"username": TEST_USER, "password": TEST_PASSWORD}).status_code == 200
        yield c


@pytest.fixture(autouse=True)
def _writes_allowed(request, monkeypatch):
    """Most tests exercise the flows themselves, so the owner's real-write lock (wg_core/write_guard.py) is opened for
    them; tests marked `real_guard` keep the real lock (default: everything locked)."""
    if request.node.get_closest_marker("real_guard"):
        return
    from wg_core import write_guard

    monkeypatch.setattr(write_guard, "check", lambda op, fqdn: None)


def pytest_configure(config):
    config.addinivalue_line("markers", "real_guard: keep the real-write lock as in production")
