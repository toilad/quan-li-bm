"""Cài đặt API: secrets stored encrypted, never returned; owner settings win over env; Google OAuth web flow; read-only check."""
import json
import urllib.parse

import httpx
import respx
from sqlalchemy import text

from wg_core import runtime_config
from wg_core.db import engine

CLIENT_JSON = json.dumps({"web": {"client_id": "cid.apps.googleusercontent.com", "client_secret": "csecret-value", "redirect_uris": ["x"], "javascript_origins": ["y"]}})




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
        tok = m.post("https://oauth2.googleapis.com/token").mock(return_value=httpx.Response(200, json={"access_token": "a", "refresh_token": "1//refresh", "scope": "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file"}))
        back = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "the-code"})
    assert back.status_code == 302 and back.headers["location"].endswith("/settings?google=connected")
    sent = urllib.parse.parse_qs(tok.calls[0].request.content.decode())
    assert sent["code_verifier"] and sent["client_secret"] == ["csecret-value"]
    s = client.get("/api/settings").json()
    assert s["google"]["connected"] and "1//refresh" not in json.dumps(s)
    # a replayed / forged callback is refused
    again = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "x"})
    assert "google=error" in again.headers["location"]


def test_google_connection_without_the_drive_permission_is_refused(client):
    client.put("/api/settings", json={"name": "GOOGLE_OAUTH_CLIENT_JSON", "value": CLIENT_JSON})
    q = urllib.parse.parse_qs(urllib.parse.urlparse(client.get("/api/google/oauth/start").headers["location"]).query)
    with respx.mock(assert_all_called=False) as m:  # the owner unticked Drive on Google's consent screen
        m.post("https://oauth2.googleapis.com/token").mock(return_value=httpx.Response(200, json={
            "access_token": "a", "refresh_token": "1//refresh", "scope": "https://www.googleapis.com/auth/spreadsheets"}))
        back = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "the-code"})
    assert "google=error" in back.headers["location"] and "missing_scope" in back.headers["location"] and "Drive" in back.headers["location"]
    assert not client.get("/api/settings").json()["google"]["connected"]


def test_google_check_is_read_only(client, monkeypatch):
    monkeypatch.setenv("SHEET_ID", "TESTSHEET")
    with respx.mock(assert_all_called=False) as m:
        m.post("https://oauth2.googleapis.com/token").respond(200, json={"access_token": "t", "expires_in": 3600})
        m.get("https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET").respond(200, json={"properties": {"title": "Bản sao thử"}, "sheets": [{"properties": {"title": "Phoi US"}}]})
        m.get(url__startswith="https://sheets.googleapis.com/v4/spreadsheets/TESTSHEET/values/").respond(200, json={"values": [["Title"], ["A", "B"]]})
        m.get("https://www.googleapis.com/drive/v3/about").respond(200, json={"user": {"emailAddress": "owner@example.com"}})
        m.get(url__startswith="https://www.googleapis.com/drive/v3/files/TESTFOLDER").respond(404, json={"error": {"message": "File not found"}})
        r = client.get("/api/google/check").json()
        writes = [c for c in m.calls if c.request.method in ("PUT", "POST", "PATCH", "DELETE") and "oauth2" not in str(c.request.url)]
    assert r["sheet"]["title"] == "Bản sao thử" and r["sheet"]["tab_found"] and r["drive"]["account"] == "owner@example.com"
    assert writes == []
    assert r["sheet"]["data_starts_at_row"] == 3 and r["sheet"]["header_rows"] == [["Title"], ["A", "B"]]
    assert r["drive"]["folder_ok"] is False and "drive.file" in r["drive"]["folder_problem"]  # a hand-made folder is flagged


def test_first_data_row_is_a_setting(client, monkeypatch):
    from tests.mocks import FakeSheet
    from wg_core.integrations.google import Sheets

    assert client.put("/api/settings", json={"name": "SHEET_FIRST_ROW", "value": "0"}).status_code == 422
    assert client.put("/api/settings", json={"name": "SHEET_FIRST_ROW", "value": "abc"}).status_code == 422
    assert client.put("/api/settings", json={"name": "SHEET_FIRST_ROW", "value": "2"}).status_code == 200
    sheet = FakeSheet({3: {"A": "Row Three LLC"}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        Sheets().read_rows()
        Sheets().append_row(["X"] * 11)
        ranges = [str(c.request.url) for c in m.calls if "spreadsheets/TESTSHEET/values" in str(c.request.url)]
    assert any("A2%3AL" in u for u in ranges) and any("A2%3AK" in u and ":append" in u for u in ranges)


def test_client_id_and_secret_fields_are_enough_to_connect(client):
    assert client.put("/api/settings", json={"name": "GOOGLE_CLIENT_ID", "value": "not-an-id"}).status_code == 422
    assert client.put("/api/settings", json={"name": "GOOGLE_CLIENT_ID", "value": "123-abc.apps.googleusercontent.com"}).status_code == 200
    assert client.put("/api/settings", json={"name": "GOOGLE_CLIENT_SECRET", "value": "secret-value-xyz"}).status_code == 200
    body = client.get("/api/settings").text
    assert "secret-value-xyz" not in body  # never returned
    r = client.get("/api/google/oauth/start")
    q = urllib.parse.parse_qs(urllib.parse.urlparse(r.headers["location"]).query)
    assert r.status_code == 302 and q["client_id"] == ["123-abc.apps.googleusercontent.com"]
    with respx.mock(assert_all_called=False) as m:
        tok = m.post("https://oauth2.googleapis.com/token").mock(return_value=httpx.Response(200, json={
            "access_token": "a", "refresh_token": "1//r", "scope": "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file"}))
        back = client.get("/api/google/oauth/callback", params={"state": q["state"][0], "code": "c"})
    assert back.headers["location"].endswith("google=connected")
    assert urllib.parse.parse_qs(tok.calls[0].request.content.decode())["client_secret"] == ["secret-value-xyz"]


def test_saving_a_setting_logs_its_name_never_its_value(client, caplog):
    import logging

    with caplog.at_level(logging.WARNING, logger="qlbm.settings"):
        assert client.put("/api/settings", json={"name": "CPANEL_TOKEN_N3", "value": "TOPSECRETVALUE0123456789"}).status_code == 200
        assert client.put("/api/settings", json={"name": "CPANEL_ADDON_API_N3", "value": "nope"}).status_code == 422
    text = caplog.text
    assert "CPANEL_TOKEN_N3 saved" in text and "CPANEL_ADDON_API_N3 NOT saved (HTTP 422" in text
    assert "TOPSECRETVALUE0123456789" not in text and "nope" not in text.split("HTTP 422")[0]


def test_a_wrong_paste_is_refused_for_keys_and_tokens(client):
    sentence = "Anh ơi, phần cPanel của nick 3 đã kết nối thật bằng token riêng của app"
    for name in ("INET_API_KEY_N3", "CPANEL_TOKEN_N3", "CPANEL_USER_N3"):
        r = client.put("/api/settings", json={"name": name, "value": sentence})
        assert r.status_code == 422 and "nhầm" in r.text or "không dấu" in r.text
        assert sentence not in r.text  # the refused value is not echoed back
    assert client.put("/api/settings", json={"name": "INET_API_KEY_N3", "value": "inet_sk_AbC123xyz"}).status_code == 200
    assert client.put("/api/settings", json={"name": "CPANEL_TOKEN_N3", "value": "ABCDEFGHIJKLMNOPQRSTUVWXYZ012345"}).status_code == 200
    assert client.put("/api/settings", json={"name": "CPANEL_USER_N3", "value": "cpuser"}).status_code == 200


def test_a_bad_value_already_stored_gives_a_clear_error_not_a_crash():
    import os

    import pytest

    from wg_core.integrations.cpanel import CPanel
    from wg_core.integrations.errors import NotConfigured
    from wg_core.integrations.inet import Inet

    os.environ.update({"INET_API_KEY_N2": "khoá sai có dấu", "CPANEL_USER_N2": "u2", "CPANEL_TOKEN_N2": "token có dấu"})
    try:
        with pytest.raises(NotConfigured, match="INET_API_KEY_N2 hợp lệ"):
            Inet("n2")
        with pytest.raises(NotConfigured, match="CPANEL_TOKEN_N2 hợp lệ"):
            CPanel("n2", "h.example")
    finally:
        for k in ("INET_API_KEY_N2", "CPANEL_USER_N2", "CPANEL_TOKEN_N2"):
            os.environ.pop(k, None)


def test_anthropic_key_wrong_paste_is_refused(client):
    assert client.put("/api/settings", json={"name": "ANTHROPIC_API_KEY", "value": "đây là một câu dán nhầm"}).status_code == 422
    assert client.put("/api/settings", json={"name": "ANTHROPIC_API_KEY", "value": "sk-ant-api03-abcDEF123"}).status_code == 200
