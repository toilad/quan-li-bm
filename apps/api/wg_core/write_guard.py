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
It locks itself again (after_job, relock): when the trial job ends (done or not), when any write job fails / conflicts /
is blocked, and whenever the API or the worker starts.
"""
from datetime import datetime, timezone

from .integrations.errors import NotAvailable

KEY = "dns_write"
OPS = {"dns": "Thêm bản ghi A (iNET)", "host": "Tạo miền trên cPanel", "upload": "Tải website lên hosting", "ssl": "Chạy AutoSSL",
       "phone": "Mua số điện thoại (có phí)"}
DEFAULT = {"enabled": False, "trial_fqdn": "", "ops": [], "trial_passed": False, "trial_job": None,
           "web_trial_passed": False, "web_trial_job": None, "changed_at": None, "locked_reason": None,
           "also": []}  # other names the owner approved for this opening (e.g. AutoSSL on both trial domains)


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
    if op == "phone":  # no trial: each purchase also needs the owner's confirmation of its cost, and relocks after
        return None
    passed = sw["trial_passed"] if op in ("dns", "host") else sw["web_trial_passed"]
    allowed = {(sw["trial_fqdn"] or "").lower()} | {n.lower() for n in sw.get("also") or []}
    if not passed and fqdn.lower() not in allowed:
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


WRITE_JOBS = {"domain_create": "fqdn", "web_build": "domain"}  # job kind → payload key holding the name it writes


def relock(s, reason: str) -> bool:
    """Lock again (keeps the trial results, so the owner can reopen later). True if it was open."""
    from .models import AppSetting

    sw = load(s)
    if not sw["enabled"]:
        return False
    sw.update(enabled=False, also=[], locked_reason=reason, changed_at=datetime.now(timezone.utc).isoformat())
    s.merge(AppSetting(key=KEY, value=sw))
    return True


def after_job(s, kind: str, status: str, payload: dict) -> str | None:
    """Called by the job runner when a job stops. Locks again when:
    - a write job ended in failed / conflict / blocked (whatever the mode: nothing spreads after a problem);
    - the trial job ended in any final state (done too): the next step needs the owner to reopen it.
    Returns the reason when it locked."""
    if kind not in WRITE_JOBS or status not in ("done", "failed", "conflict", "blocked"):
        return None
    sw = load(s)
    if not sw["enabled"]:
        return None
    name = (payload.get(WRITE_JOBS[kind]) or "").lower()
    trial = name == (sw["trial_fqdn"] or "").lower()
    if status != "done":
        reason = f"Tự khoá: việc {kind} cho {name} kết thúc “{status}”"
    elif trial:
        reason = f"Tự khoá: việc thử {kind} cho {name} đã xong — anh mở lại nếu muốn làm bước tiếp"
    else:
        return None
    relock(s, reason)
    return reason
