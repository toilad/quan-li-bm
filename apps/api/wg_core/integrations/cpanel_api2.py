"""cPanel API 2 adapter — only for creating an addon domain.

Why it exists: the official page of AddonDomain::addaddondomain is in the cPanel API 2 reference, which says API 2 is
deprecated but "no equivalent UAPI function exists"
(https://api.docs.cpanel.net/cpanel-api-2/cpanel-api-2-modules-addondomain/cpanel-api-2-functions-addondomain-addaddondomain).
The UAPI reference for 11.138 lists an AddonDomain::addaddondomain too; the two official pages disagree, so the app
does not pick one silently: CPANEL_ADDON_API_<nick> chooses ("api2" by default, "uapi" = CPanel.add_addon_uapi).
Neither has been called on a real account yet — the first approved trial write shows which one the host accepts.

Call (cPanel port 2083, same API token header; the Manage API Tokens page says tokens are for "cPanel API 2 and UAPI"):
  GET /json-api/cpanel?cpanel_jsonapi_apiversion=2&cpanel_jsonapi_module=AddonDomain&cpanel_jsonapi_func=addaddondomain
      &newdomain=<name>&subdomain=<label>&dir=<path relative to home>
Response: {"cpanelresult": {"apiversion": 2, "func", "module", "event": {"result": 1}, "data": [{"result", "reason"}],
           "error"?: "…"}}. The read-only listaddondomains on nick 3 answered in this shape (checked live).
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
        items = res.get("data") or []
        if items and not _ok(items[0].get("result")):
            raise Permanent(f"cPanel API 2 AddonDomain::addaddondomain: {items[0].get('reason') or 'lỗi không rõ'}")
        if not items and not _ok((res.get("event") or {}).get("result")):
            raise Permanent("cPanel API 2 AddonDomain::addaddondomain: không báo thành công")


def add_addon(cp: CPanel, fqdn: str, dir_: str, api: str) -> str:
    """Create the addon with the API the owner chose for this nick. Returns the API name used."""
    if api == "uapi":
        cp.add_addon_uapi(fqdn, dir_)
        return "UAPI AddonDomain::addaddondomain"
    CPanelApi2(cp).add_addon(fqdn, dir_)
    return "cPanel API 2 AddonDomain::addaddondomain"
