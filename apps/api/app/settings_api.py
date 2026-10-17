"""“Cài đặt API” endpoints + Google OAuth for the web app + a read-only Google check.

Secrets are write-only through this API: they are encrypted server-side (runtime_config) and never returned.
Google OAuth (web server flow, PKCE): the owner clicks “Kết nối Google”, consents on Google, and the callback stores
the refresh token encrypted. Works with an OAuth client of type “Web application” (server) — the redirect URI to
register is shown on the settings page — or “Desktop app” on this machine (loopback http://localhost).
Endpoints: https://accounts.google.com/o/oauth2/v2/auth · https://oauth2.googleapis.com/token ·
Sheets GET spreadsheets/{id}?fields=… · Drive GET about?fields=user
"""
import base64
import hashlib
import json
import secrets
import time
import urllib.parse

import httpx
from fastapi import APIRouter, HTTPException
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from wg_core import runtime_config
from wg_core.db import session_scope
from wg_core.integrations import google
from wg_core.models import AppSetting

router = APIRouter()
AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def _public(name: str, default: str) -> str:
    return runtime_config.get(name, default).rstrip("/")


def redirect_uri() -> str:
    return _public("PUBLIC_API_URL", "http://localhost:8000") + "/api/google/oauth/callback"


@router.get("/api/settings")
def get_settings():
    oc = google.oauth_client()
    return {
        "fields": runtime_config.describe(),
        "google": {"mode": google.auth_mode(), "client_type": ("web" if oc and oc.get("redirect_uris") and "javascript_origins" in oc else "desktop/khác") if oc else None,
                   "redirect_uri": redirect_uri(), "connected": bool(google.refresh_token())},
    }


class PutSetting(BaseModel):
    name: str
    value: str


@router.put("/api/settings")
def put_setting(body: PutSetting):
    if body.name not in runtime_config.FIELDS:
        raise HTTPException(422, "Không có trường cài đặt này")
    if body.name in runtime_config.SET_ONLY_BY_SERVER and body.value.strip():
        raise HTTPException(422, "Trường này chỉ được ghi qua nút Kết nối Google")
    if body.name == "SHEET_FIRST_ROW" and body.value.strip() and not (body.value.strip().isdigit() and 1 <= int(body.value) <= 1000):
        raise HTTPException(422, "Dòng bắt đầu dữ liệu phải là số từ 1 đến 1000")
    if body.name == "GOOGLE_OAUTH_CLIENT_JSON" and body.value.strip():
        try:
            data = json.loads(body.value)
            cfg = data.get("web") or data.get("installed") or data
            assert cfg.get("client_id") and cfg.get("client_secret")
        except (ValueError, AssertionError, AttributeError):
            raise HTTPException(422, "Không phải file JSON OAuth client hợp lệ (cần client_id và client_secret)")
    runtime_config.put(body.name, body.value)
    google._token_cache.clear()
    return {"ok": True, "name": body.name, "set": bool(body.value.strip())}


@router.get("/api/google/oauth/start")
def oauth_start():
    oc = google.oauth_client()
    if not oc:
        raise HTTPException(422, "Chưa có OAuth client — dán file JSON ở mục Google trước")
    verifier = secrets.token_urlsafe(64)
    state = secrets.token_urlsafe(24)
    with session_scope() as s:
        s.merge(AppSetting(key="google_oauth_pending", value={"state": state, "verifier": verifier, "at": time.time()}))
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": oc["client_id"], "redirect_uri": redirect_uri(), "response_type": "code", "scope": google.OAUTH_SCOPES,
        "access_type": "offline", "prompt": "consent", "include_granted_scopes": "true",
        "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    })
    return RedirectResponse(url, status_code=302)


@router.get("/api/google/oauth/callback")
def oauth_callback(state: str = "", code: str = "", error: str = ""):
    web = _public("PUBLIC_WEB_URL", "http://localhost:3210") + "/settings"
    with session_scope() as s:
        pending = s.get(AppSetting, "google_oauth_pending")
        p = dict(pending.value) if pending else {}
        if pending:
            s.delete(pending)
    if error or not code or not p or p.get("state") != state or time.time() - p.get("at", 0) > 900:
        return RedirectResponse(f"{web}?google=error&reason={urllib.parse.quote(error or 'state')}", status_code=302)
    oc = google.oauth_client()
    try:
        r = httpx.post(google.TOKEN_URL, timeout=30, data={
            "code": code, "client_id": oc["client_id"], "client_secret": oc.get("client_secret", ""), "redirect_uri": redirect_uri(),
            "grant_type": "authorization_code", "code_verifier": p["verifier"]})
    except httpx.TransportError:
        return RedirectResponse(f"{web}?google=error&reason=network", status_code=302)
    body = r.json() if r.content else {}
    if r.status_code != 200 or "refresh_token" not in body:
        return RedirectResponse(f"{web}?google=error&reason={urllib.parse.quote(str(body.get('error', r.status_code)))}", status_code=302)
    # Google's consent screen lets the owner untick a permission: without both, saving PDFs would fail later.
    granted, missing = set(body.get("scope", "").split()), []
    for scope, label in ((google.OAUTH_SCOPES.split()[0], "Sheets"), (google.OAUTH_SCOPES.split()[1], "Drive")):
        if body.get("scope") and scope not in granted:
            missing.append(label)
    if missing:
        return RedirectResponse(f"{web}?google=error&reason={urllib.parse.quote('missing_scope:' + '+'.join(missing))}", status_code=302)
    runtime_config.put("GOOGLE_TOKEN", json.dumps({"refresh_token": body["refresh_token"], "scope": body.get("scope", "")}))
    google._token_cache.clear()
    return RedirectResponse(f"{web}?google=connected", status_code=302)


@router.get("/api/google/check")
def google_check():
    """Read-only: the Sheet's title and tabs, its first two rows, and the Drive account. Nothing is written."""
    out: dict = {"mode": google.auth_mode()}
    google.require_google(need_sheet=True)
    sid, tab = google.sheet_id(), google.sheet_tab()
    with google._client() as c:
        meta = google._check(c.get(f"{google.SHEETS}/{sid}", headers=google._auth(c),
                                   params={"fields": "properties.title,sheets.properties.title"}), "Sheets đọc thông tin")
        tabs = [x["properties"]["title"] for x in meta.get("sheets", [])]
        out["sheet"] = {"title": meta.get("properties", {}).get("title"), "tabs": tabs, "tab_found": tab in tabs, "tab": tab}
        if tab in tabs:
            head = google._check(c.get(f"{google.SHEETS}/{sid}/values/{google._a1(tab, 'A1:L2')}", headers=google._auth(c)), "Sheets đọc tiêu đề")
            out["sheet"]["header_rows"] = head.get("values", [])
        about = google._check(c.get("https://www.googleapis.com/drive/v3/about", headers=google._auth(c), params={"fields": "user(emailAddress)"}), "Drive đọc tài khoản")
        folder = runtime_config.get("DRIVE_FOLDER_ID")
        out["drive"] = {"account": about.get("user", {}).get("emailAddress"), "folder": folder or "app sẽ tự tạo khi lưu PDF đầu tiên",
                        "folder_ok": None}
        if folder:  # with OAuth (drive.file) the app only sees folders it created itself: check before the first save
            fr = c.get(f"{google.DRIVE_FILES}/{folder}", headers=google._auth(c), params={"fields": "id,name,mimeType", "supportsAllDrives": "true"})
            out["drive"]["folder_ok"] = fr.status_code == 200 and fr.json().get("mimeType") == "application/vnd.google-apps.folder"
            if not out["drive"]["folder_ok"]:
                out["drive"]["folder_problem"] = ("app không truy cập được thư mục này (quyền drive.file chỉ thấy thư mục do app tạo) — "
                                                  "để trống “ID thư mục Drive” để app tự tạo")
        out["sheet"]["data_starts_at_row"] = google.first_row()
    return out
