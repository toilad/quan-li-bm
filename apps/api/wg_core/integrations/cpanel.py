"""cPanel UAPI over HTTPS with an API token (api.docs.cpanel.net).

Auth:  Authorization: cpanel <user>:<token>   →  https://<host>:2083/execute/<Module>/<function>
Used (all documented, see docs/API-RESEARCH.md):
  SubDomain::addsubdomain, SubDomain::listsubdomains, DomainInfo::single_domain_data, DomainInfo::list_domains,
  AddonDomain::listaddondomains (read), AddonDomain::addaddondomain (UAPI, available from cPanel 138 — the official
  spec 11.138.0.10 says x-cpanel-api-version UAPI, x-cpanel-available-version "cPanel 138"; older servers use the
  cPanel API 2 adapter in cpanel_api2.py),
  Fileman::list_files, Fileman::upload_files (POST multipart, file-0…), SSL::start_autossl_check,
  SSL::is_autossl_check_in_progress, SSL::get_autossl_problems,
  StatsBar::get_stats (display=cpanelversion), DNS::has_local_authority (read-only).
Response envelope — two shapes are documented, both are read by _envelope():
  - top level {"status": 1|0, "data", "errors", "messages", "warnings", "metadata"}: what /execute/ actually answers
    over HTTP (checked live on nick 3 for old and new functions alike, tests/fixtures/cpanel_live_samples.json), and
    what the spec gives for functions added in 138 (AddonDomain::*);
  - {"apiversion": 3, "func", "module", "result": {"status", "data", "errors", …}}: what the spec gives for older
    functions (StatsBar::get_stats, DomainInfo::*, SubDomain::*, Fileman::*, SSL::*) — the `uapi` command-line output.
  Anything else is refused (never guessed).
Every write goes through write_guard.check first (locked unless the owner allowed it).
"""
import re

import httpx

from . import http

from .. import write_guard
from ..config import env_secret
from .errors import NotConfigured, Permanent, Transient


class CPanel:
    def __init__(self, nick_id: str, host: str):
        key = nick_id.upper()
        self.nick_id = nick_id
        self.user, self.token = env_secret(f"CPANEL_USER_{key}"), env_secret(f"CPANEL_TOKEN_{key}")
        missing = [n for n, v in ((f"CPANEL_USER_{key}", self.user), (f"CPANEL_TOKEN_{key}", self.token)) if not v]
        if missing or not host:
            raise NotConfigured(f"cPanel {nick_id}", missing + ([] if host else ["địa chỉ cPanel"]))
        self.host = host
        self.base = f"https://{host}:2083/execute"

    def request(self, path: str, what: str, params: dict | None = None, files: dict | None = None) -> dict:
        """HTTP to https://<host>:2083/<path> with this nick's token. Returns the JSON body. The token never appears
        in an error message (only the cPanel user and the function name do)."""
        headers = {"Authorization": f"cpanel {self.user}:{self.token}"}
        url = f"https://{self.host}:2083/{path}"
        try:
            with http.client(timeout=120) as c:
                if files:
                    r = c.post(url, headers=headers, params=params or {}, files=files)
                else:
                    r = c.get(url, headers=headers, params=params or {})
        except httpx.TransportError as e:
            raise Transient(f"cPanel {what}: lỗi mạng ({type(e).__name__})") from None
        if r.status_code == 429 or r.status_code >= 500:
            raise Transient(f"cPanel {what}: HTTP {r.status_code}")
        if r.status_code in (401, 403):
            raise NotConfigured(f"cPanel {self.user}", [f"token hợp lệ / quyền {what} (HTTP {r.status_code})"])
        if r.status_code >= 400:
            raise Permanent(f"cPanel {what}: HTTP {r.status_code}")
        try:
            body = r.json()
        except ValueError:
            # without valid credentials /execute/ answers HTTP 200 with the cPanel login page (checked live)
            if "html" in r.headers.get("content-type", "") and "login" in r.text[:50000].lower():
                raise NotConfigured(f"cPanel {self.user}", [f"token được chấp nhận — cPanel trả trang đăng nhập cho {what}"]) from None
            raise Transient(f"cPanel {what}: trả về không phải JSON (HTTP {r.status_code}) — có thể đang bảo trì / tường lửa") from None
        if not isinstance(body, dict):
            raise Permanent(f"cPanel {what}: phản hồi không đúng định dạng")
        return body

    @staticmethod
    def _envelope(body: dict, what: str) -> dict:
        if "status" in body:
            return body
        inner = body.get("result")
        if isinstance(inner, dict) and "status" in inner:
            return inner
        raise Permanent(f"cPanel {what}: phản hồi không có “status” (cũng không có “result.status”) — không phải định dạng UAPI")

    def _call(self, module: str, fn: str, params: dict | None = None, files: dict | None = None):
        res = self._envelope(self.request(f"execute/{module}/{fn}", f"{module}::{fn}", params, files), f"{module}::{fn}")
        if res.get("status") != 1:
            raise Permanent(f"cPanel {module}::{fn}: {'; '.join(res.get('errors') or ['lỗi không rõ'])}")
        return res.get("data")

    def version(self) -> str:
        """StatsBar::get_stats display=cpanelversion. Live (138): `value` = "138.0 (build 15)", `count` = null."""
        for item in self._call("StatsBar", "get_stats", {"display": "cpanelversion"}) or []:
            if item.get("name") == "cpanelversion" or item.get("id") == "cpanelversion":
                return str(item.get("value") or item.get("count") or "")
        return ""

    def major_version(self) -> int | None:
        """138 for "138.0 (build 15)" or "11.138.0.15"; None when it cannot be read."""
        m = re.match(r"\s*(?:11\.)?(\d+)", self.version())
        return int(m.group(1)) if m else None

    # ── domains (read) ──
    def subdomain(self, fqdn: str) -> dict | None:
        """Entry from SubDomain::listsubdomains for exactly this FQDN (has dir, basedir, rootdomain)."""
        rx = "^" + re.escape(fqdn) + "$"
        for d in self._call("SubDomain", "listsubdomains", {"regex": rx}) or []:
            if d.get("domain", "").lower() == fqdn.lower():
                return d
        return None

    def addon(self, fqdn: str) -> dict | None:
        """Entry from AddonDomain::listaddondomains for exactly this domain (domain, subdomain, rootdomain, basedir, dir)."""
        rx = "^" + re.escape(fqdn) + "$"
        for d in self._call("AddonDomain", "listaddondomains", {"regex": rx}) or []:
            if d.get("domain", "").lower() == fqdn.lower():
                return d
        return None

    def domain_data(self, domain: str) -> dict | None:
        """DomainInfo::single_domain_data — main/addon domains (documentroot, type, ip). None if not on the account."""
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

    def classify(self, domain: str) -> str:
        """What `domain` is on this account: main | addon | alias (parked) | subdomain | absent."""
        d, x = self.list_domains(), domain.lower()
        if x == (d.get("main_domain") or "").lower():
            return "main"
        for kind, key in (("addon", "addon_domains"), ("alias", "parked_domains"), ("subdomain", "sub_domains")):
            if x in {n.lower() for n in d.get(key) or []}:
                return kind
        return "absent"

    def creation_mode(self, root: str) -> dict:
        """How a new name under `root` is created here, read from cPanel (never assumed per nick).
        Returns {mode: subdomain|addon|None, kind, parent, ip, docroot, reason}. mode None = stop (reason says why):
          main / addon root  → subdomain of the root (needs its document root and IP)
          not on the account → addon domain parked on the primary domain (needs the primary's document root and IP)
          alias / subdomain / unreadable → stop: the parent of a new name is not clear."""
        d = self.list_domains()
        main = (d.get("main_domain") or "").lower()
        if not main:
            return {"mode": None, "kind": "unknown", "reason": "cPanel không cho biết miền chính của tài khoản — dừng"}
        kind = self.classify(root)
        if kind == "alias":
            return {"mode": None, "kind": kind, "reason": f"{root} là alias (parked) của một miền khác trên cPanel — không dùng làm miền gốc"}
        if kind == "subdomain":
            return {"mode": None, "kind": kind, "reason": f"{root} là subdomain trên cPanel — không xác định được miền cha cho tên mới"}
        parent = root.lower() if kind in ("main", "addon") else main
        pd = self.domain_data(parent) or {}
        if not pd.get("documentroot"):
            return {"mode": None, "kind": kind, "reason": f"cPanel không cho biết document root của {parent} — dừng"}
        return {"mode": "subdomain" if kind in ("main", "addon") else "addon", "kind": kind, "parent": parent,
                "main": main, "ip": (pd.get("ip") or "").strip(), "docroot": pd["documentroot"], "reason": None}

    def folder_exists(self, rel: str) -> bool:
        """Is there already a folder `public_html/<name>` (rel = "public_html/<name>")? Fileman::list_files, read-only."""
        parent, _, name = rel.strip("/").rpartition("/")
        data = self._call("Fileman", "list_files", {"dir": parent, "types": "dir"}) or []
        items = data.get("dirs", []) if isinstance(data, dict) else data
        return any((x.get("file") or "").lower() == name.lower() for x in items)

    def inventory(self) -> dict:
        """Read-only: domains on the account by type, and how many addons follow the public_html/<name> pattern."""
        d = self.list_domains()
        addons = self._call("AddonDomain", "listaddondomains") or []
        linked = {(a.get("fullsubdomain") or "").lower() for a in addons}
        subs = [x for x in d.get("sub_domains") or [] if x.lower() not in linked]  # every addon also has its own subdomain
        return {"main": d.get("main_domain") or "", "addon": len(addons), "parked": len(d.get("parked_domains") or []),
                "subdomain": len(subs),
                "addon_docroot_pattern": sum(1 for a in addons if a.get("basedir") == f"public_html/{a.get('domain')}"),
                "names": sorted({x.lower() for x in [d.get("main_domain") or ""] + (d.get("addon_domains") or []) if x}),
                "aliases": sorted(x.lower() for x in d.get("parked_domains") or [])}

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

    # ── domains (write — each one behind the owner's lock) ──
    def add_subdomain(self, label: str, rootdomain: str, dir_: str) -> None:
        write_guard.check("host", f"{label}.{rootdomain}")
        self._call("SubDomain", "addsubdomain", {"domain": label, "rootdomain": rootdomain, "dir": dir_})

    def add_addon_uapi(self, fqdn: str, dir_: str) -> None:
        """UAPI AddonDomain::addaddondomain — in the UAPI spec for 11.138, but the API 2 page says there is no UAPI
        equivalent. Used only when the owner picks CPANEL_ADDON_API_<nick> = uapi."""
        write_guard.check("host", fqdn)
        self._call("AddonDomain", "addaddondomain", {"newdomain": fqdn, "subdomain": fqdn, "dir": dir_, "disallowdot": 0})

    # ── files ──
    def list_files(self, dir_: str) -> set[str]:
        """Fileman::list_files → names of the files in dir (relative dirs resolve against the home directory)."""
        data = self._call("Fileman", "list_files", {"dir": dir_, "types": "file"}) or []
        items = data.get("files", []) if isinstance(data, dict) else data
        return {x.get("file") for x in items if x.get("file") and x.get("type", "file") == "file"}

    def upload_files(self, dir_: str, files: dict[str, bytes], fqdn: str, overwrite: bool = False) -> dict:
        """overwrite=0: an existing file is never replaced (cPanel fails that file with "already exists")."""
        write_guard.check("upload", fqdn)
        multipart = {f"file-{i}": (name, data) for i, (name, data) in enumerate(files.items())}
        return self._call("Fileman", "upload_files", {"dir": dir_, "overwrite": 1 if overwrite else 0}, files=multipart)

    # ── SSL ──
    def start_autossl(self, fqdn: str) -> None:
        write_guard.check("ssl", fqdn)
        self._call("SSL", "start_autossl_check")

    def autossl_in_progress(self) -> bool:
        return bool(self._call("SSL", "is_autossl_check_in_progress"))

    def autossl_problems(self, domain: str) -> list[str]:
        return [p.get("problem", "") for p in (self._call("SSL", "get_autossl_problems") or []) if p.get("domain", "").lower() == domain.lower()]
