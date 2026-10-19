"""The hosting's "Let's Encrypt SSL" cPanel plugin (FleetSSL cPanel 0.21.0 on the iNET servers) — the Issue button.

The plugin's JSON API lives under /frontend/ and refuses cPanel API tokens (HTTP 403, checked live 2026-10-19).
So the app opens a real cPanel session the official way, exactly like OnePortal's "Đăng nhập cPanel":
  iNET  GET  /hosting?name=<hosting>        → hosting id                          (key scope: Hosting, GET)
  iNET  POST /hosting/{id}/login            → data = JSON string of WHM create_user_session:
        {"metadata": {"result": 1, "reason": "Created session"}, "data": {"url", "cp_security_token", "session", "expires"}}
  GET   data.url (follows redirects)        → cPanel session cookie + /cpsessNNN/ path            (checked live, nick 2)
  Plugin (documented: cpanel.fleetssl.com › For developers › Plugin JSON API):
  GET  …/cpsessNNN/frontend/jupiter/letsencrypt/letsencrypt.live.cgi?api_version=1&api_function=list-certificates
  POST …&api_function=issue-certificate  virtual_host, dns_identifiers, challenge_method (http-01), dry_run
  Answer: {"success": true|false, "errors": [..]|null, "data": {"virtual_hosts": {"<vhost>": {…}}}} (seen live)
No password, no cookie of the owner's browser. One issue call = one virtual host, exactly the name given — never an
account-wide AutoSSL run. The session lives only for this object (it is not stored anywhere).
"""
import json
import re

import httpx

from . import http
from .. import write_guard
from .errors import NotConfigured, Permanent, Transient
from .inet import Inet

THEME = "jupiter"


class FleetSSL:
    def __init__(self, nick_id: str, hosting: str):
        self.nick_id, self.hosting = nick_id, (hosting or "").lower()
        if not self.hosting:
            raise NotConfigured(f"Let's Encrypt (plugin) {nick_id}", ["tên hosting của nick"])
        self.inet = Inet(nick_id)  # NotConfigured when this nick has no iNET key
        self._client: httpx.Client | None = None
        self._base = ""

    # ── session through the iNET API ──
    def _login(self):
        found = self.inet._get("/hosting", {"name": self.hosting})
        items = [h for h in (found or {}).get("content") or [] if (h.get("domainName") or "").lower() == self.hosting]
        if not items:
            raise Permanent(f"iNET: không thấy hosting {self.hosting} trong tài khoản của nick {self.nick_id}")
        raw = self.inet._call("POST", f"/hosting/{int(items[0]['id'])}/login")
        try:
            session = json.loads(raw) if isinstance(raw, str) else raw
        except ValueError:
            raise Permanent("iNET /hosting/{id}/login: phản hồi không đọc được") from None
        url = ((session or {}).get("data") or {}).get("url") or (raw.get("url") if isinstance(raw, dict) else "")
        if not url or ((session or {}).get("metadata") or {}).get("result", 1) != 1:
            raise Permanent(f"iNET không tạo được phiên cPanel: {((session or {}).get('metadata') or {}).get('reason') or 'không có URL'}")
        client = http.client(timeout=180, follow_redirects=True)
        try:
            r = client.get(url)
        except httpx.TransportError as e:
            client.close()
            raise Transient(f"Vào cPanel: lỗi mạng ({type(e).__name__})") from None
        m = re.search(r"/cpsess\d+/", str(r.url))
        if r.status_code != 200 or not m:
            client.close()
            raise Permanent(f"Vào cPanel bằng URL của iNET không thành công (HTTP {r.status_code})")
        self._client = client
        self._base = f"https://{r.url.host}:{r.url.port or 2083}{m.group(0)}frontend/{THEME}/letsencrypt/letsencrypt.live.cgi"

    def close(self):
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()

    def _call(self, method: str, function: str, data: dict | None = None) -> dict:
        what = f"Let's Encrypt plugin {function}"
        if not self._client:
            self._login()
        try:
            r = self._client.request(method, self._base, params={"api_version": 1, "api_function": function}, data=data,
                                     headers={"Accept": "application/json"})
        except httpx.TransportError as e:
            raise Transient(f"{what}: lỗi mạng ({type(e).__name__})") from None
        if r.status_code in (401, 403):
            raise Permanent(f"{what}: cPanel từ chối phiên (HTTP {r.status_code})")
        if r.status_code == 429 or r.status_code >= 500:
            raise Transient(f"{what}: HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            raise Transient(f"{what}: trả về không phải JSON (HTTP {r.status_code})") from None
        if not isinstance(body, dict) or "success" not in body:
            raise Permanent(f"{what}: phản hồi không đúng định dạng của plugin")
        if body["success"] is not True:
            raise Permanent(f"{what}: {'; '.join(str(e) for e in (body.get('errors') or ['không thành công']))}")
        return body.get("data") or {}

    def certificates(self) -> dict:
        """{virtual_host: {dns_identifiers, challenge_method, …}} for every certificate the plugin manages (read-only)."""
        return (self._call("GET", "list-certificates") or {}).get("virtual_hosts") or {}

    def issue(self, fqdn: str, dry_run: bool = False) -> dict:
        """The Issue button for exactly this name: its own virtual host, only this DNS identifier, HTTP validation."""
        if not dry_run:
            write_guard.check("ssl", fqdn)
        data = {"virtual_host": fqdn, "dns_identifiers": fqdn, "challenge_method": "http-01", "dry_run": 1 if dry_run else 0}
        return self._call("POST", "issue-certificate", data)
