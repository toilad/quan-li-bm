"""Google Sheets API v4 + Drive API v3.

Two ways to authenticate (developers.google.com):
- OAuth 2.0 for the owner's own Google account (installed-app flow, see scripts/google_auth.py). Needed for a
  personal Gmail Drive: "Service accounts don't have storage quota and can't own any files" — they can only upload
  into shared drives (Google Workspace). Scopes: spreadsheets + drive.file (the app only sees files it created).
- Service account (JWT bearer) — fine for Sheets; for Drive only with a folder in a shared drive.
Token endpoint: POST https://oauth2.googleapis.com/token (refresh_token / jwt-bearer grants).

Sheets: GET values/{range} · PUT values/{range}?valueInputOption=RAW|USER_ENTERED · POST values/{range}:append
Drive:  POST upload/drive/v3/files?uploadType=multipart (appProperties qlbm_md5) ·
        GET drive/v3/files?q=appProperties has { key='qlbm_md5' and value='…' } · POST drive/v3/files (folder)
Codes are written with RAW so leading zeros, dots and dashes stay exactly as text.
"""
import base64
import json
import re
import time
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import quote

import httpx
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

from ..config import settings
from ..runtime_config import get as cfg
from .errors import NotConfigured, Permanent, Transient

TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
DRIVE_FILES = "https://www.googleapis.com/drive/v3/files"
SA_SCOPES = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive"
OAUTH_SCOPES = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive.file"
FOLDER_NAME = "Quản Lí BM — Phôi PDF"

_token_cache: dict[str, tuple[str, float]] = {}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _check(resp: httpx.Response, what: str) -> dict:
    if resp.status_code == 429 or resp.status_code >= 500:
        ra = resp.headers.get("retry-after")
        raise Transient(f"{what}: HTTP {resp.status_code}", float(ra) if ra and ra.isdigit() else None)
    if resp.status_code >= 400:
        try:
            body = resp.json()
            err = body.get("error", {})
            msg = err.get("message", resp.text[:300]) if isinstance(err, dict) else f"{err} {body.get('error_description', '')}".strip()
        except ValueError:
            msg = resp.text[:300]
        if "invalid_grant" in str(msg):
            raise NotConfigured("Google", [
                "bấm “Kết nối lại” ở Cài đặt API — quyền Google đã hết hạn hoặc bị thu hồi (ứng dụng Google Cloud còn ở "
                f"chế độ Testing thì quyền chỉ sống 7 ngày: chuyển sang In production) ({msg})"])
        if resp.status_code in (401, 403) and any(k in str(msg).lower() for k in ("insufficient", "scope", "permission")):
            raise NotConfigured("Google", [f"quyền cho {what} (khi kết nối hãy tick đủ Sheets và Drive) — {msg}"])
        raise Permanent(f"{what}: HTTP {resp.status_code} — {msg}")
    return resp.json() if resp.content else {}


def token_file() -> Path:
    return settings().data_dir / "google_token.json"


def oauth_client() -> dict | None:
    """OAuth client config: Client ID + Client secret typed on the settings page (secret stored encrypted), or the
    whole JSON pasted there, or GOOGLE_OAUTH_CLIENT_FILE."""
    cid, secret = (cfg("GOOGLE_CLIENT_ID") or "").strip(), (cfg("GOOGLE_CLIENT_SECRET") or "").strip()
    if cid and secret:
        return {"client_id": cid, "client_secret": secret, "redirect_uris": [], "javascript_origins": [], "kind": "web"}
    raw = cfg("GOOGLE_OAUTH_CLIENT_JSON")
    if not raw:
        f = settings().google_oauth_client_file
        raw = Path(f).read_text(encoding="utf-8") if f and Path(f).exists() else ""
    if not raw:
        return None
    data = json.loads(raw)
    return data.get("web") or data.get("installed") or data


def refresh_token() -> str | None:
    raw = cfg("GOOGLE_TOKEN")
    if raw:
        return json.loads(raw)["refresh_token"] if raw.lstrip().startswith("{") else raw
    if token_file().exists():
        return json.loads(token_file().read_text(encoding="utf-8")).get("refresh_token")
    return None


def sheet_id() -> str:
    return cfg("SHEET_ID")


def sheet_tab() -> str:
    return cfg("SHEET_TAB", "Phoi US")


def auth_mode() -> str | None:
    """'oauth' when the owner authorised the app, 'service_account' when only a SA file is set, else None."""
    s = settings()
    if oauth_client() and refresh_token():
        return "oauth"
    if s.google_service_account_file and Path(s.google_service_account_file).exists():
        return "service_account"
    return None


def require_google(need_sheet=True, need_drive=False):
    s, mode = settings(), auth_mode()
    missing = []
    if not mode:
        missing.append("Kết nối Google (Cài đặt API → dán OAuth client loại Web application → bấm Kết nối Google)")
    if need_sheet and not sheet_id():
        missing.append("SHEET_ID")
    if need_drive and mode == "service_account" and not cfg("DRIVE_FOLDER_ID"):
        missing.append("DRIVE_FOLDER_ID trong Shared Drive (service account không upload được vào Drive cá nhân) — hoặc dùng OAuth")
    if missing:
        raise NotConfigured("Google", missing)


def _oauth_token(client: httpx.Client) -> str:
    cached = _token_cache.get("oauth")
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    oc = oauth_client()
    data = _check(client.post(TOKEN_URL, data={"grant_type": "refresh_token", "refresh_token": refresh_token(),
                                               "client_id": oc["client_id"], "client_secret": oc.get("client_secret", "")}), "Google token")
    _token_cache["oauth"] = (data["access_token"], time.time() + int(data.get("expires_in", 3600)))
    return data["access_token"]


def _sa_token(client: httpx.Client) -> str:
    s = settings()
    cached = _token_cache.get(s.google_service_account_file)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    info = json.loads(Path(s.google_service_account_file).read_text(encoding="utf-8"))
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(json.dumps({"iss": info["client_email"], "scope": SA_SCOPES, "aud": TOKEN_URL, "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(info["private_key"].encode(), password=None)
    sig = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{header}.{claims}.{_b64(sig)}"
    data = _check(client.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}), "Google token")
    _token_cache[s.google_service_account_file] = (data["access_token"], now + int(data.get("expires_in", 3600)))
    return data["access_token"]


def access_token(client: httpx.Client) -> str:
    return _oauth_token(client) if auth_mode() == "oauth" else _sa_token(client)


class _Transport(httpx.HTTPTransport):
    """Network errors (timeout, reset, DNS) become Transient, so the job retries instead of failing."""

    def handle_request(self, request):
        try:
            return super().handle_request(request)
        except httpx.TransportError as e:
            raise Transient(f"Google: lỗi mạng ({type(e).__name__}) — tự thử lại") from None


def _client() -> httpx.Client:
    return httpx.Client(timeout=60, transport=_Transport())


def _auth(c: httpx.Client) -> dict:
    return {"Authorization": f"Bearer {access_token(c)}"}


def _a1(tab: str, cells: str) -> str:
    return quote("'" + tab.replace("'", "''") + f"'!{cells}", safe="")  # A1 notation: ' inside a sheet name is doubled


COLS = "ABCDEFGHIJKL"
FIRST_DATA_ROW = 3  # default: row 1 = title, row 2 = header (Cài đặt › "Dòng bắt đầu dữ liệu" overrides it)


def first_row() -> int:
    """The first Sheet row that holds data; rows above it (title, header, notes) are never read or written."""
    try:
        return max(1, int(cfg("SHEET_FIRST_ROW") or FIRST_DATA_ROW))
    except ValueError:
        return FIRST_DATA_ROW


@dataclass
class SheetRow:
    row: int
    cells: dict  # {"A": "...", ..., "L": "..."}


class Sheets:
    def __init__(self):
        require_google(need_sheet=True)
        self.id, self.tab = sheet_id(), sheet_tab()

    def read_rows(self) -> list[SheetRow]:
        first = first_row()
        with _client() as c:
            data = _check(c.get(f"{SHEETS}/{self.id}/values/{_a1(self.tab, f'A{first}:L')}",
                                headers=_auth(c), params={"valueRenderOption": "FORMATTED_VALUE"}), "Sheets đọc")
        rows = []
        for i, vals in enumerate(data.get("values", [])):
            cells = {col: (vals[j] if j < len(vals) else "") for j, col in enumerate(COLS)}
            rows.append(SheetRow(first + i, {k: str(v) for k, v in cells.items()}))
        return rows

    def read_cell(self, cell: str) -> str:
        with _client() as c:
            data = _check(c.get(f"{SHEETS}/{self.id}/values/{_a1(self.tab, cell)}", headers=_auth(c)), "Sheets đọc ô")
        vals = data.get("values") or [[""]]
        return str(vals[0][0]) if vals and vals[0] else ""

    def write_cell(self, cell: str, value: str, user_entered: bool = False) -> dict:
        """RAW by default (text stays text). USER_ENTERED only for formulas the app builds itself (K = HYPERLINK)."""
        with _client() as c:
            return _check(c.put(f"{SHEETS}/{self.id}/values/{_a1(self.tab, cell)}", headers=_auth(c),
                                params={"valueInputOption": "USER_ENTERED" if user_entered else "RAW"},
                                json={"values": [[value]]}), "Sheets ghi ô")

    def append_row(self, values: list[str]) -> int:
        """Append A..K (L untouched). Returns the sheet row number written."""
        with _client() as c:
            data = _check(c.post(f"{SHEETS}/{self.id}/values/{_a1(self.tab, f'A{first_row()}:K')}:append",
                                 headers=_auth(c), params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                                 json={"values": [values]}), "Sheets thêm dòng")
        rng = data.get("updates", {}).get("updatedRange", "")
        m = re.search(r"![A-Z]+(\d+)", rng)
        if not m:
            raise Permanent(f"Sheets không trả về vị trí dòng đã ghi ({rng!r})")
        return int(m.group(1))


def hyperlink_formula(url: str, label: str = "Xem phôi") -> str:
    return '=HYPERLINK("{}","{}")'.format(url.replace('"', ""), label)


class Drive:
    def __init__(self):
        require_google(need_sheet=False, need_drive=True)
        self.configured_folder = cfg("DRIVE_FOLDER_ID")

    def folder_id(self) -> str:
        """DRIVE_FOLDER_ID if set; otherwise the app's own folder (created once, remembered in the database)."""
        if self.configured_folder:
            return self.configured_folder
        from ..db import session_scope
        from ..models import AppSetting

        with session_scope() as db:
            row = db.get(AppSetting, "drive_folder")
            if row and row.value.get("id"):
                return row.value["id"]
            with _client() as c:
                res = _check(c.post(DRIVE_FILES, headers=_auth(c), params={"fields": "id", "supportsAllDrives": "true"},
                                    json={"name": FOLDER_NAME, "mimeType": "application/vnd.google-apps.folder"}), "Drive tạo thư mục")
            db.merge(AppSetting(key="drive_folder", value={"id": res["id"], "name": FOLDER_NAME}))
            return res["id"]

    def find_by_md5(self, md5: str) -> dict | None:
        """A file this app already uploaded with the same content (appProperties qlbm_md5) — never upload twice."""
        q = f"appProperties has {{ key='qlbm_md5' and value='{md5}' }} and trashed = false"
        with _client() as c:
            res = _check(c.get(DRIVE_FILES, headers=_auth(c), params={"q": q, "fields": "files(id,md5Checksum,webViewLink)",
                                                                      "supportsAllDrives": "true", "includeItemsFromAllDrives": "true"}), "Drive tìm file")
        files = res.get("files", [])
        return files[0] if files else None

    def upload_pdf(self, name: str, content: bytes, md5: str) -> dict:
        """Uploads the original bytes unchanged. Returns {id, md5Checksum, webViewLink}."""
        meta = {"name": name, "parents": [self.folder_id()], "mimeType": "application/pdf", "appProperties": {"qlbm_md5": md5}}
        boundary = "qlbm" + str(int(time.time() * 1000))
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
                f"--{boundary}\r\nContent-Type: application/pdf\r\n\r\n").encode() + content + f"\r\n--{boundary}--".encode()
        with _client() as c:
            return _check(c.post(DRIVE_UPLOAD, headers={**_auth(c), "Content-Type": f"multipart/related; boundary={boundary}"},
                                 params={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id,md5Checksum,webViewLink"},
                                 content=body), "Drive upload")
