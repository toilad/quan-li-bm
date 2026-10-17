"""cPanel UAPI over HTTPS with an API token (api.docs.cpanel.net).

Auth:  Authorization: cpanel <user>:<token>   →  https://<host>:2083/execute/<Module>/<function>
Used (all documented, see docs/API-RESEARCH.md):
  SubDomain::addsubdomain, SubDomain::listsubdomains, DomainInfo::single_domain_data, DomainInfo::list_domains,
  AddonDomain::addaddondomain, AddonDomain::listaddondomains (UAPI module, documented for 11.138; listing checked live),
  Fileman::upload_files (POST multipart, file-0…), SSL::start_autossl_check,
  SSL::is_autossl_check_in_progress, SSL::get_autossl_problems,
  StatsBar::get_stats (display=cpanelversion, read-only; docs checked against API version 11.138)
  DNS::has_local_authority (read-only: is this server authoritative for the domain's DNS?)
Responses: result.status 1 = ok, 0 = failed (errors in result.errors).
"""
import re

import httpx

from . import http

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
            with http.client(timeout=120) as c:
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
        try:
            res = r.json().get("result", {})
        except ValueError:
            raise Transient(f"cPanel {module}::{fn}: trả về không phải JSON (HTTP {r.status_code}) — có thể đang bảo trì / tường lửa") from None
        if res.get("status") != 1:
            raise Permanent(f"cPanel {module}::{fn}: {'; '.join(res.get('errors') or ['lỗi không rõ'])}")
        return res.get("data")

    def version(self) -> str:
        """StatsBar::get_stats display=cpanelversion → item `count` = the server's cPanel version."""
        for item in self._call("StatsBar", "get_stats", {"display": "cpanelversion"}) or []:
            if item.get("name") == "cpanelversion" or item.get("id") == "cpanelversion":
                return str(item.get("count") or item.get("value") or "")
        return ""

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

    def has_local_authority(self, domain: str) -> dict:
        """DNS::has_local_authority → {domain, local_authority: 1|0, nameservers, zone, error?}."""
        for d in self._call("DNS", "has_local_authority", {"domain": domain}) or []:
            if (d.get("domain") or "").lower() == domain.lower():
                return d
        return {}

    def list_domains(self) -> dict:
        """DomainInfo::list_domains → {main_domain, addon_domains, sub_domains, parked_domains} (read-only)."""
        return self._call("DomainInfo", "list_domains", {"hide_temporary_domains": 1}) or {}

    def add_subdomain(self, label: str, rootdomain: str, dir_: str) -> None:
        self._call("SubDomain", "addsubdomain", {"domain": label, "rootdomain": rootdomain, "dir": dir_})

    def addon(self, fqdn: str) -> dict | None:
        """Entry from AddonDomain::listaddondomains for exactly this domain (domain, subdomain, rootdomain, basedir, dir)."""
        rx = "^" + re.escape(fqdn) + "$"
        for d in self._call("AddonDomain", "listaddondomains", {"regex": rx}) or []:
            if d.get("domain", "").lower() == fqdn.lower():
                return d
        return None

    def add_addon(self, fqdn: str, dir_: str) -> None:
        """AddonDomain::addaddondomain (UAPI, documented for 11.138). Same shape as the 922 addons already on nick 3:
        subdomain label = the whole new domain (dots kept, disallowdot=0), parked on the primary domain."""
        self._call("AddonDomain", "addaddondomain", {"newdomain": fqdn, "subdomain": fqdn, "dir": dir_, "disallowdot": 0})

    def creation_mode(self, root: str) -> dict:
        """How a new name under `root` is created on this account, read from cPanel (never assumed per nick):
        root is on the account (main / addon / parked) → subdomain of it; otherwise → addon domain on the primary domain.
        Returns {mode, ip, main?}. The IP is the root's (subdomain) or the primary domain's (addon)."""
        dd = self.domain_data(root)
        if dd:
            return {"mode": "subdomain", "ip": (dd.get("ip") or "").strip()}
        main = (self.list_domains().get("main_domain") or "").lower()
        if not main:
            raise Permanent("cPanel không cho biết tên miền chính của tài khoản")
        md = self.domain_data(main) or {}
        return {"mode": "addon", "ip": (md.get("ip") or "").strip(), "main": main}

    def inventory(self) -> dict:
        """Read-only: domains on the account by type, and the document roots of addon domains."""
        d = self.list_domains()
        addons = self._call("AddonDomain", "listaddondomains") or []
        return {"main": d.get("main_domain") or "", "addon": len(addons), "parked": len(d.get("parked_domains") or []),
                "subdomain": len(d.get("sub_domains") or []) - len(addons),  # every addon also has its own subdomain
                "addon_docroot_pattern": sum(1 for a in addons if a.get("basedir") == f"public_html/{a.get('domain')}"),
                "names": sorted({x.lower() for x in [d.get("main_domain") or ""] + (d.get("addon_domains") or []) + (d.get("parked_domains") or []) if x})}

    def document_root(self, domain: str) -> tuple[str, str] | None:
        """(path relative to home, API used) — read from cPanel, never assumed."""
        add = self.addon(domain)
        if add and (add.get("basedir") or add.get("dir")):
            return add.get("basedir") or add.get("dir"), "AddonDomain::listaddondomains"
        sub = self.subdomain(domain)
        if sub:
            return sub.get("basedir") or sub.get("dir"), "SubDomain::listsubdomains"
        data = self.domain_data(domain)
        if data and data.get("documentroot"):
            return data["documentroot"], "DomainInfo::single_domain_data"
        return None

    # ── files ──
    def list_files(self, dir_: str) -> set[str]:
        """Fileman::list_files → names of the files in dir (relative dirs resolve against the home directory)."""
        data = self._call("Fileman", "list_files", {"dir": dir_, "types": "file"}) or []
        items = data.get("files", []) if isinstance(data, dict) else data
        return {x.get("file") for x in items if x.get("file") and x.get("type", "file") == "file"}

    def upload_files(self, dir_: str, files: dict[str, bytes], overwrite: bool = False) -> dict:
        """overwrite=0: an existing file is never replaced (cPanel fails that file with "already exists")."""
        multipart = {f"file-{i}": (name, data) for i, (name, data) in enumerate(files.items())}
        return self._call("Fileman", "upload_files", {"dir": dir_, "overwrite": 1 if overwrite else 0}, files=multipart)

    # ── SSL ──
    def start_autossl(self) -> None:
        self._call("SSL", "start_autossl_check")

    def autossl_in_progress(self) -> bool:
        return bool(self._call("SSL", "is_autossl_check_in_progress"))

    def autossl_problems(self, domain: str) -> list[str]:
        return [p.get("problem", "") for p in (self._call("SSL", "get_autossl_problems") or []) if p.get("domain", "").lower() == domain.lower()]
