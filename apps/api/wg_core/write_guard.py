"""One lock in front of every real write to the owner's hosting and DNS, checked at the lowest layer (the API client
call itself), so no code path can write while it is locked.

State = AppSetting "dns_write" (the owner's switch on the Settings page):
  enabled      False → everything is LOCKED (the default)
  trial_fqdn   the one name the owner approved for the first try
  ops          which writes the owner allowed: dns (iNET A record), host (create the name on cPanel),
               upload (website files), ssl (AutoSSL check). Nothing is allowed by default.
  trial_passed      the domain trial (A record + cPanel + DNS + B) finished → dns/host for other names
  web_trial_passed  the website trial (upload + SSL + C) finished on the trial name → upload/ssl for other names
Until the matching trial has passed, a write is allowed only for the trial name.
"""
from datetime import datetime, timezone

from .integrations.errors import NotAvailable

KEY = "dns_write"
OPS = {"dns": "Thêm bản ghi A (iNET)", "host": "Tạo miền trên cPanel", "upload": "Tải website lên hosting", "ssl": "Chạy AutoSSL"}
DEFAULT = {"enabled": False, "trial_fqdn": "", "ops": [], "trial_passed": False, "trial_job": None,
           "web_trial_passed": False, "web_trial_job": None, "changed_at": None}


def load(s=None) -> dict:
    from .models import AppSetting

    if s is not None:
        row = s.get(AppSetting, KEY)
        return {**DEFAULT, **(row.value if row else {})}
    from .db import session_scope

    with session_scope() as s2:
        row = s2.get(AppSetting, KEY)
        return {**DEFAULT, **(row.value if row else {})}


def why_not(sw: dict, op: str, fqdn: str) -> str | None:
    """None = this write is allowed now."""
    name = OPS[op]
    if not sw["enabled"]:
        return f"Ghi thật đang KHOÁ — chưa {name.lower()} cho {fqdn}. Anh mở ở Cài đặt › Ghi thật khi duyệt chạy thử"
    if op not in (sw.get("ops") or []):
        return f"Anh chưa cho phép thao tác “{name}” — bật nó ở Cài đặt › Ghi thật"
    passed = sw["trial_passed"] if op in ("dns", "host") else sw["web_trial_passed"]
    if not passed and fqdn.lower() != (sw["trial_fqdn"] or "").lower():
        return f"Đang chạy thử: “{name}” chỉ được làm cho miền thử {sw['trial_fqdn'] or '(chưa đặt)'}, không phải {fqdn}"
    return None


def check(op: str, fqdn: str) -> None:
    """Raise NotAvailable unless the owner's switch allows this write for this name right now."""
    if why := why_not(load(), op, fqdn):
        raise NotAvailable("Ghi thật", why)


def mark_web_trial(s, fqdn: str, job_id: int) -> bool:
    from .models import AppSetting

    sw = load(s)
    if sw["enabled"] and not sw["web_trial_passed"] and fqdn.lower() == (sw["trial_fqdn"] or "").lower():
        sw.update(web_trial_passed=True, web_trial_job=job_id, changed_at=datetime.now(timezone.utc).isoformat())
        s.merge(AppSetting(key=KEY, value=sw))
        return True
    return False
