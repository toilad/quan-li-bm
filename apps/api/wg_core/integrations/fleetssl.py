"""The hosting's "Let's Encrypt SSL" cPanel plugin (FleetSSL cPanel 0.21.0 on the iNET servers) — the Issue button.

Why a separate client: the plugin's JSON API lives under /frontend/ and refuses cPanel API tokens (HTTP 403, checked
live 2026-10-19). Its documentation (cpanel.fleetssl.com › For developers › Plugin JSON API) authenticates with the
cPanel username + password. The owner chose to store that password (encrypted, never shown) only for this plugin:
everything else keeps using the API token.

  GET  …/letsencrypt/letsencrypt.live.cgi?api_version=1&api_function=list-certificates
  POST …/letsencrypt/letsencrypt.live.cgi?api_version=1&api_function=issue-certificate
       virtual_host, dns_identifiers, challenge_method (http-01), dry_run (staging, result discarded)
Answer (seen live): {"success": true|false, "errors": [..]|null, "data": {"virtual_hosts": {"<vhost>": {"virtual_host",
  "dns_identifiers", "challenge_method", "cpanel_cert_id", …}}}}
One call = one virtual host and exactly the names given: never an account-wide AutoSSL run.
"""
import httpx

from . import http
from .. import write_guard
from ..config import env_secret
from .errors import NotConfigured, Permanent, Transient

THEME = "jupiter"


class FleetSSL:
    def __init__(self, nick_id: str, host: str):
        key = nick_id.upper()
        self.user, self.password = env_secret(f"CPANEL_USER_{key}"), env_secret(f"CPANEL_PASSWORD_{key}")
        missing = [n for n, v in ((f"CPANEL_USER_{key}", self.user), (f"CPANEL_PASSWORD_{key}", self.password)) if not v]
        if missing or not host:
            raise NotConfigured(f"Let's Encrypt (plugin) {nick_id}", missing + ([] if host else ["địa chỉ cPanel"]))
        self.url = f"https://{host}:2083/frontend/{THEME}/letsencrypt/letsencrypt.live.cgi"

    def _call(self, method: str, function: str, data: dict | None = None) -> dict:
        what = f"Let's Encrypt plugin {function}"
        try:
            with http.client(timeout=180) as c:
                r = c.request(method, self.url, params={"api_version": 1, "api_function": function}, data=data,
                              auth=(self.user, self.password), headers={"Accept": "application/json"})
        except httpx.TransportError as e:
            raise Transient(f"{what}: lỗi mạng ({type(e).__name__})") from None
        if r.status_code in (401, 403):
            raise NotConfigured(f"cPanel {self.user}", [f"mật khẩu cPanel đúng cho {what} (HTTP {r.status_code})"])
        if r.status_code == 429 or r.status_code >= 500:
            raise Transient(f"{what}: HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            if "login" in r.text[:50000].lower():
                raise NotConfigured(f"cPanel {self.user}", [f"mật khẩu cPanel đúng — cPanel trả trang đăng nhập cho {what}"]) from None
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
