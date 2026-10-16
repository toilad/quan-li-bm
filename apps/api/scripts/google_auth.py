"""One-time Google consent for the owner's account (OAuth 2.0 for installed apps, loopback + PKCE).

    python -m scripts.google_auth

Needs GOOGLE_OAUTH_CLIENT_FILE in .env (OAuth client of type "Desktop app" from Google Cloud Console).
Opens the browser; the OWNER signs in and approves. Scopes: Google Sheets + drive.file (only files this app creates).
The refresh token is written to data/google_token.json (gitignored) — never printed.
Endpoints: https://accounts.google.com/o/oauth2/v2/auth · https://oauth2.googleapis.com/token
"""
import base64
import hashlib
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")

import httpx  # noqa: E402

from wg_core.config import settings  # noqa: E402
from wg_core.integrations.google import OAUTH_SCOPES, TOKEN_URL, token_file  # noqa: E402

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"


def main():
    client_file = settings().google_oauth_client_file
    if not client_file or not Path(client_file).exists():
        raise SystemExit("Đặt GOOGLE_OAUTH_CLIENT_FILE trong apps/api/.env (file JSON của OAuth client loại Desktop app).")
    data = json.loads(Path(client_file).read_text(encoding="utf-8"))
    cfg = data.get("installed") or data.get("web") or data
    verifier = secrets.token_urlsafe(64)
    challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    state = secrets.token_urlsafe(16)
    result: dict = {}

    class Handler(http.server.BaseHTTPRequestHandler):
        def do_GET(self):  # noqa: N802
            q = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
            result.update({k: v[0] for k, v in q.items()})
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write("Xong — có thể đóng tab này và quay lại cửa sổ dòng lệnh.".encode())
            threading.Thread(target=self.server.shutdown, daemon=True).start()

        def log_message(self, *args):
            pass

    server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
    redirect = f"http://127.0.0.1:{server.server_port}"
    url = AUTH_URL + "?" + urllib.parse.urlencode({
        "client_id": cfg["client_id"], "redirect_uri": redirect, "response_type": "code", "scope": OAUTH_SCOPES,
        "access_type": "offline", "prompt": "consent", "code_challenge": challenge, "code_challenge_method": "S256", "state": state,
    })
    print("Mở trình duyệt để anh đăng nhập Google và cấp quyền (Sheets + file do app tạo trên Drive).")
    print("Nếu trình duyệt không tự mở, dán link này vào trình duyệt:\n" + url)
    webbrowser.open(url)
    server.serve_forever()
    if result.get("state") != state or "code" not in result:
        raise SystemExit(f"Không nhận được mã cấp quyền ({result.get('error', 'không rõ')}).")
    r = httpx.post(TOKEN_URL, data={"code": result["code"], "client_id": cfg["client_id"], "client_secret": cfg.get("client_secret", ""),
                                    "redirect_uri": redirect, "grant_type": "authorization_code", "code_verifier": verifier}, timeout=30)
    body = r.json()
    if r.status_code != 200 or "refresh_token" not in body:
        raise SystemExit(f"Đổi mã lấy token thất bại: {body.get('error')} {body.get('error_description', '')}")
    out = token_file()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"refresh_token": body["refresh_token"], "scope": body.get("scope", "")}), encoding="utf-8")
    print(f"Đã lưu quyền truy cập vào {out} (không đưa vào Git). Phạm vi: {body.get('scope', '')}")


if __name__ == "__main__":
    main()
