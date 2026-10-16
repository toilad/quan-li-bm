"""Google Sheets API v4 + Drive API v3 with a service account (OAuth 2.0 JWT bearer flow).

Endpoints (developers.google.com):
- Token:   POST https://oauth2.googleapis.com/token  (grant_type=urn:ietf:params:oauth:grant-type:jwt-bearer)
- Sheets:  GET  /v4/spreadsheets/{id}/values/{range}
           PUT  /v4/spreadsheets/{id}/values/{range}?valueInputOption=RAW
           POST /v4/spreadsheets/{id}/values/{range}:append?valueInputOption=RAW&insertDataOption=INSERT_ROWS
- Drive:   POST https://www.googleapis.com/upload/drive/v3/files?uploadType=multipart&supportsAllDrives=true
           (fields=id,md5Checksum,webViewLink)
Codes are written with valueInputOption=RAW so leading zeros, dots and dashes stay exactly as text.
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
from .errors import NotConfigured, Permanent, Transient

TOKEN_URL = "https://oauth2.googleapis.com/token"
SHEETS = "https://sheets.googleapis.com/v4/spreadsheets"
DRIVE_UPLOAD = "https://www.googleapis.com/upload/drive/v3/files"
SCOPES = "https://www.googleapis.com/auth/spreadsheets https://www.googleapis.com/auth/drive"

_token_cache: dict[str, tuple[str, float]] = {}


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _check(resp: httpx.Response, what: str) -> dict:
    if resp.status_code == 429 or resp.status_code >= 500:
        ra = resp.headers.get("retry-after")
        raise Transient(f"{what}: HTTP {resp.status_code}", float(ra) if ra and ra.isdigit() else None)
    if resp.status_code >= 400:
        try:
            msg = resp.json().get("error", {}).get("message", resp.text[:300])
        except ValueError:
            msg = resp.text[:300]
        raise Permanent(f"{what}: HTTP {resp.status_code} — {msg}")
    return resp.json() if resp.content else {}


def require_google(need_sheet=True, need_drive=False):
    s = settings()
    missing = []
    if not s.google_service_account_file or not Path(s.google_service_account_file).exists():
        missing.append("GOOGLE_SERVICE_ACCOUNT_FILE (file JSON service account)")
    if need_sheet and not s.sheet_id:
        missing.append("SHEET_ID")
    if need_drive and not s.drive_folder_id:
        missing.append("DRIVE_FOLDER_ID")
    if missing:
        raise NotConfigured("Google", missing)


def access_token(client: httpx.Client) -> str:
    s = settings()
    cached = _token_cache.get(s.google_service_account_file)
    if cached and cached[1] > time.time() + 60:
        return cached[0]
    info = json.loads(Path(s.google_service_account_file).read_text(encoding="utf-8"))
    now = int(time.time())
    header = _b64(json.dumps({"alg": "RS256", "typ": "JWT"}).encode())
    claims = _b64(json.dumps({"iss": info["client_email"], "scope": SCOPES, "aud": TOKEN_URL, "iat": now, "exp": now + 3600}).encode())
    key = serialization.load_pem_private_key(info["private_key"].encode(), password=None)
    sig = key.sign(f"{header}.{claims}".encode(), padding.PKCS1v15(), hashes.SHA256())
    assertion = f"{header}.{claims}.{_b64(sig)}"
    data = _check(client.post(TOKEN_URL, data={"grant_type": "urn:ietf:params:oauth:grant-type:jwt-bearer", "assertion": assertion}), "Google token")
    _token_cache[s.google_service_account_file] = (data["access_token"], now + int(data.get("expires_in", 3600)))
    return data["access_token"]


def _client() -> httpx.Client:
    return httpx.Client(timeout=60)


def _auth(c: httpx.Client) -> dict:
    return {"Authorization": f"Bearer {access_token(c)}"}


def _a1(tab: str, cells: str) -> str:
    return quote(f"'{tab}'!{cells}", safe="")


COLS = "ABCDEFGHIJKL"
FIRST_DATA_ROW = 3  # row 1 = title, row 2 = header


@dataclass
class SheetRow:
    row: int
    cells: dict  # {"A": "...", ..., "L": "..."}


class Sheets:
    def __init__(self):
        require_google(need_sheet=True)
        self.s = settings()

    def read_rows(self) -> list[SheetRow]:
        with _client() as c:
            data = _check(c.get(f"{SHEETS}/{self.s.sheet_id}/values/{_a1(self.s.sheet_tab, f'A{FIRST_DATA_ROW}:L')}",
                                headers=_auth(c), params={"valueRenderOption": "FORMATTED_VALUE"}), "Sheets đọc")
        rows = []
        for i, vals in enumerate(data.get("values", [])):
            cells = {col: (vals[j] if j < len(vals) else "") for j, col in enumerate(COLS)}
            rows.append(SheetRow(FIRST_DATA_ROW + i, {k: str(v) for k, v in cells.items()}))
        return rows

    def read_cell(self, cell: str) -> str:
        with _client() as c:
            data = _check(c.get(f"{SHEETS}/{self.s.sheet_id}/values/{_a1(self.s.sheet_tab, cell)}", headers=_auth(c)), "Sheets đọc ô")
        vals = data.get("values") or [[""]]
        return str(vals[0][0]) if vals and vals[0] else ""

    def write_cell(self, cell: str, value: str) -> dict:
        with _client() as c:
            return _check(c.put(f"{SHEETS}/{self.s.sheet_id}/values/{_a1(self.s.sheet_tab, cell)}", headers=_auth(c),
                                params={"valueInputOption": "RAW"}, json={"values": [[value]]}), "Sheets ghi ô")

    def append_row(self, values: list[str]) -> int:
        """Append A..K (L untouched). Returns the sheet row number written."""
        with _client() as c:
            data = _check(c.post(f"{SHEETS}/{self.s.sheet_id}/values/{_a1(self.s.sheet_tab, f'A{FIRST_DATA_ROW}:K')}:append",
                                 headers=_auth(c), params={"valueInputOption": "RAW", "insertDataOption": "INSERT_ROWS"},
                                 json={"values": [values]}), "Sheets thêm dòng")
        rng = data.get("updates", {}).get("updatedRange", "")
        m = re.search(r"![A-Z]+(\d+)", rng)
        if not m:
            raise Permanent(f"Sheets không trả về vị trí dòng đã ghi ({rng!r})")
        return int(m.group(1))


class Drive:
    def __init__(self):
        require_google(need_sheet=False, need_drive=True)
        self.s = settings()

    def upload_pdf(self, name: str, content: bytes) -> dict:
        """Uploads the original bytes unchanged. Returns {id, md5Checksum, webViewLink}."""
        meta = {"name": name, "parents": [self.s.drive_folder_id], "mimeType": "application/pdf"}
        boundary = "qlbm" + str(int(time.time() * 1000))
        body = (f"--{boundary}\r\nContent-Type: application/json; charset=UTF-8\r\n\r\n{json.dumps(meta)}\r\n"
                f"--{boundary}\r\nContent-Type: application/pdf\r\n\r\n").encode() + content + f"\r\n--{boundary}--".encode()
        with _client() as c:
            return _check(c.post(DRIVE_UPLOAD, headers={**_auth(c), "Content-Type": f"multipart/related; boundary={boundary}"},
                                 params={"uploadType": "multipart", "supportsAllDrives": "true", "fields": "id,md5Checksum,webViewLink"},
                                 content=body), "Drive upload")
