"""Cài đặt API: secrets stored encrypted, never returned; owner settings win over env; Google OAuth web flow; read-only check."""
import json
import urllib.parse

import httpx
import pytest
import respx
from fastapi.testclient import TestClient
from sqlalchemy import text

from wg_core import runtime_config
from wg_core.db import engine

CLIENT_JSON = json.dumps({"web": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret-value", "redirect_uris": ["x"], "javascript_origins": ["y"]}})


@pytest.fixture
def client():
    from app.main import app

    with TestClient(app, follow_redirects=False) as c:
        yield c


def test_secret_is_encrypted_at_rest_and_never_returned(client):
    r = client.put("/api/settings", json={"name": "ANTHROPIC_API_KEY", "value": "sk-test-SECRET-123"})
    assert r.status_code == 200
    with engine().connect() as c:
        stored = c.execute(text("SELECT value, secret FROM stored_settings WHERE name='ANTHROPIC_API_KEY'")).one()
    assert stored.secret and "SECRET-123" not in stored.value  # Fernet token, not the key
    body = client.get("/api/settings").text
    assert "SECRET-123" not in body
    f = next(x for x in client.get("/api/settings").json()["fields"] if x["name"] == "ANTHROPIC_API_KEY")
    assert f["set"] and f["source"] == "app" and "value" not in f
    assert runtime_config.get("ANTHROPIC_API_KEY") == "sk-test-SECRET-123"  # integrations read it


def test_owner_setting_wins_over_env_and_clearing_falls_back(client, monkeypatch):
    monkeypatch.setenv("SHEET_ID", "FROM_ENV")
    client.put("/api/settings", json={"name": "SHEET_ID", "value": "FROM_APP"})
    assert runtime_config.get("SHEET_ID") == "FROM_APP"
    client.put("/api/settings", json={"name": "SHEET_ID", "value": ""})
    assert runtime_config.get("SHEET_ID") == "FROM_ENV"


def test_rejects_unknown_fields_bad_client_json_and_typed_tokens(client):
    assert client.put("/api/settings", json={"name": "WHATEVER", "value": "x"}).status_code == 422
    assert client.put("/api/settings", json={"name": "GOOGLE_OAUTH_CLIENT_JSON", "value": "{}"}).status_code == 422
    assert client.put("/api/settings", json={"name": "GOOGLE_TOKEN", "value": "abc"}).status_code == 422


def test_google_web_oauth_flow_stores_refresh_token_encrypted(client):
    client.put("/api/settings", json={"name": "GOOGLE_OAUTH_CLIENT_JSON", "value": CLIENT_JSON})
    r = client.get("/api/google/oauth/start")
    assert r.status_code == 302
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)
    assert q["redirect_uri"] == ["http://localhost:8000/api/google/oauth/callback"] and q["code_challenge_method"] == ["S256"]
    assert "drive.file" in q["scope"][0] and q["access_type"] == ["offline"]
    with respx.mock(assert_all_called=False) as m:
        tok = m.post("https://oauth2.googleapis.com/token").mock(return_value=httpx.Response(200, json={"access_token": "a", "refresh_token": "1//refresh", "scope": "s"}))
        back = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "the-code"})
    assert back.status_code == 302 and back.headers["location"].endswith("/settings?google=connected")
    sent = urllib.parse.parse_qs(tok.calls[0].request.content.decode())
    assert sent["code_verifier"] and sent["client_secret"] == ["csecret-value"]
    s = client.get("/api/settings").json()
    assert s["google"]["connected"] and "1//refresh" not in json.dumps(s)
    # a replayed / forged callback is refused
    again = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "x"})
    assert "google=error" in again.headers["location"]


def test_google_check_is_read_only(client, monkeypatch):
    monkeypatch.setenv("SHEET_ID", "TESTSHEET")
    with respx.mock(assert_all_called=False) as m:
        m.post("https://oauth2.googleapis.com/token").respond(200, json={"access_token": "t", "expires_in": 3600})
        m.get("https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET").respond(200, json={"properties": {"title": "Bản sao thử"}, "sheets": [{"properties": {"title": "Phoi US"}}]})
        m.get(url__startswith="https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET/values/").respond(200, json={"values": [["Title"], ["A", "B"]]})
        m.get("https://www.googleapis.com/drive/v3/about").respond(200, json={"user": {"emailAddress": "owner@example.com"}})
        r = client.get("/api/google/check").json()
        writes = [c for c in m.calls if c.request.method in ("PUT", "POST", "PATCH", "DELETE") and "oauth2" not in str(c.request.url)]
    assert r["sheet"]["title"] == "Bản sao thử" and r["sheet"]["tab_found"] and r["drive"]["account"] == "owner@example.com"
    assert writes == []
