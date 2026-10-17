"""cPanel API 2 adapter — only for creating an addon domain.

Which API (decided per nick, from the server's own version — never one real create to "find out"):
- The UAPI spec 11.138.0.10 lists AddonDomain::addaddondomain with x-cpanel-api-version "UAPI" and
  x-cpanel-available-version "cPanel 138": the UAPI function exists from cPanel 138 on. Nick 3 runs 138.0 (build 15).
  → cPanel ≥ 138: UAPI (CPanel.add_addon_uapi). Preferred.
- The cPanel API 2 page says "no equivalent UAPI function exists" — true for servers before 138 (the page predates it)
  (https://api.docs.cpanel.net/cpanel-api-2/cpanel-api-2-modules-addondomain/cpanel-api-2-functions-addondomain-addaddondomain).
  → cPanel < 138: this API 2 adapter, the only documented way there.
- Version unreadable → stop. CPANEL_ADDON_API_<nick> = uapi | api2 overrides "auto" only if the owner sets it.
Neither has been called on a real account yet.

Call (cPanel port 2083, same API token header; the Manage API Tokens page says tokens are for "cPanel API 2 and UAPI"):
  GET /json-api/cpanel?cpanel_jsonapi_apiversion=2&cpanel_jsonapi_module=AddonDomain&cpanel_jsonapi_func=addaddondomain
      &newdomain=<name>&subdomain=<label>&dir=<path relative to home>
Response: {"cpanelresult": {"apiversion": 2 | "2", "func", "module", "event": {"result": 1}, "data": [...] | {...}, "error"?: "…"}}.
Seen live on nick 3 (tests/fixtures/cpanel_live_samples.json): listaddondomains → apiversion 2 (number), data = list;
"Access denied" → HTTP 403, apiversion "2" (string), data = {"reason", "result": "0"} (an object, not a list).
Whatever this returns, the caller confirms the result with UAPI AddonDomain::listaddondomains before going on.
"""
from .. import write_guard
from .cpanel import CPanel
from .errors import Permanent


def _ok(v) -> bool:
    return str(v) == "1"


class CPanelApi2:
    def __init__(self, cp: CPanel):
        self.cp = cp  # same nick, host, user and token — never another nick's

    def add_addon(self, fqdn: str, dir_: str) -> None:
        write_guard.check("host", fqdn)
        body = self.cp.request("json-api/cpanel", "API 2 AddonDomain::addaddondomain", {
            "cpanel_jsonapi_apiversion": 2, "cpanel_jsonapi_module": "AddonDomain", "cpanel_jsonapi_func": "addaddondomain",
            "newdomain": fqdn, "subdomain": fqdn, "dir": dir_})
        res = body.get("cpanelresult")
        if not isinstance(res, dict) or str(res.get("apiversion")) != "2":
            raise Permanent("cPanel API 2 AddonDomain::addaddondomain: phản hồi không phải định dạng API 2 (cpanelresult)")
        if res.get("error"):
            raise Permanent(f"cPanel API 2 AddonDomain::addaddondomain: {res['error']}")
        data = res.get("data")
        item = data[0] if isinstance(data, list) and data else data if isinstance(data, dict) else None  # both seen live
        if item is not None and not _ok(item.get("result")):
            raise Permanent(f"cPanel API 2 AddonDomain::addaddondomain: {item.get('reason') or 'lỗi không rõ'}")
        if item is None and not _ok((res.get("event") or {}).get("result")):
            raise Permanent("cPanel API 2 AddonDomain::addaddondomain: không báo thành công")


UAPI_SINCE = 138


def choose(cp: CPanel, setting: str) -> str:
    """"uapi" or "api2" for this nick: the owner's explicit choice, else by the server's cPanel version."""
    if setting in ("uapi", "api2"):
        return setting
    major = cp.major_version()
    if major is None:
        raise Permanent("Không đọc được phiên bản cPanel — không chọn được API tạo addon domain, dừng")
    return "uapi" if major >= UAPI_SINCE else "api2"


def add_addon(cp: CPanel, fqdn: str, dir_: str, api: str) -> str:
    """Create the addon with `api` ("uapi" | "api2", see choose()). Returns the API name used."""
    if api == "uapi":
        cp.add_addon_uapi(fqdn, dir_)
        return "UAPI AddonDomain::addaddondomain"
    CPanelApi2(cp).add_addon(fqdn, dir_)
    return "cPanel API 2 AddonDomain::addaddondomain"
