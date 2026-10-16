"""cPanel UAPI over HTTPS with an API token (api.docs.cpanel.net).

Auth:  Authorization: cpanel <user>:<token>   →  https://<host>:2083/execute/<Module>/<function>
Used (all documented, see docs/API-RESEARCH.md):
  SubDomain::addsubdomain, SubDomain::listsubdomains, DomainInfo::single_domain_data,
  Fileman::upload_files (POST multipart, file-0…), SSL::start_autossl_check,
  SSL::is_autossl_check_in_progress, SSL::get_autossl_problems
Responses: result.status 1 = ok, 0 = failed (errors in result.errors).
"""
import re

import httpx

from ..config import env_secret
from .errors import NotConfigured, Permanent, Transient


class CPanel:
    def __init__(self, nick_id: str, host: str):
        key = nick_id.upper()
        self.user, self.token = env_secret(f"CPANEL_USER_{key}"), env_secret(f"CPANEL_TOKEN_{key}")
        missing = [n for n, v in ((f"CPANEL_USER_{key}", self.user), (f"CPANEL_TOKEN_{key}", self.token)) if not v]
        if missing or not host:
            raise NotConfigured(f"cPanel {nick_id}", missing + ([] if host else ["địa chỉ cPanel"]))
        self.base = f"https://{host}:2083/execute"

    def _call(self, module: str, fn: str, params: dict | None = None, files: dict | None = None):
        headers = {"Authorization": f"cpanel {self.user}:{self.token}"}
        try:
            with httpx.Client(timeout=120) as c:
                if files:
                    r = c.post(f"{self.base}/{module}/{fn}", headers=headers, params=params or {}, files=files)
                else:
                    r = c.get(f"{self.base}/{module}/{fn}", headers=headers, params=params or {})
        except httpx.TransportError as e:
            raise Transient(f"cPanel {module}::{fn}: {e}") from e
        if r.status_code == 429 or r.status_code >= 500:
            raise Transient(f"cPanel {module}::{fn}: HTTP {r.status_code}")
        if r.status_code in (401, 403):
            raise NotConfigured(f"cPanel {self.user}", [f"token hợp lệ / quyền {module} (HTTP {r.status_code})"])
        if r.status_code >= 400:
            raise Permanent(f"cPanel {module}::{fn}: HTTP {r.status_code}")
        res = r.json().get("result", {})
        if res.get("status") != 1:
            raise Permanent(f"cPanel {module}::{fn}: {'; '.join(res.get('errors') or ['lỗi không rõ'])}")
        return res.get("data")

    # ── domains ──
    def subdomain(self, fqdn: str) -> dict | None:
        """Entry from SubDomain::listsubdomains for exactly this FQDN (has dir, basedir, rootdomain)."""
        rx = "^" + re.escape(fqdn) + "$"
        for d in self._call("SubDomain", "listsubdomains", {"regex": rx}) or []:
            if d.get("domain", "").lower() == fqdn.lower():
                return d
        return None

    def domain_data(self, domain: str) -> dict | None:
        """DomainInfo::single_domain_data — main/addon domains (documentroot, type). None if not on the account."""
        try:
            return self._call("DomainInfo", "single_domain_data", {"domain": domain})
        except Permanent:
            return None

    def list_domains(self) -> dict:
        """DomainInfo::list_domains → {main_domain, addon_domains, sub_domains, parked_domains} (read-only)."""
        return self._call("DomainInfo", "list_domains", {"hide_temporary_domains": 1}) or {}

    def add_subdomain(self, label: str, rootdomain: str, dir_: str) -> None:
        self._call("SubDomain", "addsubdomain", {"domain": label, "rootdomain": rootdomain, "dir": dir_})

    def document_root(self, domain: str) -> tuple[str, str] | None:
        """(path relative to home, API used) — read from cPanel, never assumed."""
        sub = self.subdomain(domain)
        if sub:
            return sub.get("basedir") or sub.get("dir"), "SubDomain::listsubdomains"
        data = self.domain_data(domain)
        if data and data.get("documentroot"):
            return data["documentroot"], "DomainInfo::single_domain_data"
        return None

    # ── files ──
    def upload_files(self, dir_: str, files: dict[str, bytes]) -> dict:
        """overwrite=0: an existing file is never replaced (the call reports it as failed)."""
        multipart = {f"file-{i}": (name, data) for i, (name, data) in enumerate(files.items())}
        return self._call("Fileman", "upload_files", {"dir": dir_, "overwrite": 0}, files=multipart)

    # ── SSL ──
    def start_autossl(self) -> None:
        self._call("SSL", "start_autossl_check")

    def autossl_in_progress(self) -> bool:
        return bool(self._call("SSL", "is_autossl_check_in_progress"))

    def autossl_problems(self, domain: str) -> list[str]:
        return [p.get("problem", "") for p in (self._call("SSL", "get_autossl_problems") or []) if p.get("domain", "").lower() == domain.lower()]
