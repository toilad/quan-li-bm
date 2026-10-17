"""Real DNS writes are guarded three ways:

1. Switch (AppSetting "dns_write"), OFF by default. Only the owner turns it on.
2. Trial: while it is on but no trial has passed, a run may contain exactly ONE subdomain, the one the owner named.
   When that job finishes (A record + cPanel + DNS verified + B written), batch runs are allowed.
3. Preview: before any run, a read-only check over the APIs (cPanel domain + hosting IP, the domain in THIS nick's
   iNET account, its nameservers / DNS provider, records already using the name, public DNS). The owner sees every
   subdomain / root / nick / IP and confirms; the run then takes exactly that plan (single use, 30 minutes).
"""
import secrets
from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import Session

from ...integrations import net
from ...integrations.cpanel import CPanel
from ...integrations.errors import IntegrationError
from ...integrations.inet import Inet, dns_provider, record_label
from ...models import AppSetting, Nick, RootDomain

KEY = "dns_write"
PLAN_MINUTES = 30
DEFAULT = {"enabled": False, "trial_fqdn": "", "trial_passed": False, "trial_job": None, "changed_at": None}


def get_switch(s: Session) -> dict:
    row = s.get(AppSetting, KEY)
    return {**DEFAULT, **(row.value if row else {})}


def mode(sw: dict) -> str:
    if not sw["enabled"]:
        return "off"
    return "batch" if sw["trial_passed"] else "trial"


def set_switch(s: Session, enabled: bool | None = None, trial_fqdn: str | None = None) -> dict:
    from .service import LABEL_RX

    sw = get_switch(s)
    if trial_fqdn is not None:
        t = trial_fqdn.strip().lower()
        if t:
            label, _, root = t.partition(".")
            r = s.get(RootDomain, root)
            if not r or not r.selected:
                raise ValueError(f"Miền thử phải nằm dưới một miền gốc đã tích chọn (không có / chưa tích: {root or '—'})")
            if not LABEL_RX.match(label):
                raise ValueError("Tên miền phụ chỉ gồm a–z, 0–9, “-”")
        if t != sw["trial_fqdn"]:
            sw.update(trial_fqdn=t, trial_passed=False, trial_job=None)
    if enabled is not None:
        if enabled and not sw["trial_passed"] and not sw["trial_fqdn"]:
            raise ValueError("Chỉ định miền thử trước khi bật ghi DNS thật")
        sw["enabled"] = enabled
    sw["changed_at"] = datetime.now(timezone.utc).isoformat()
    s.merge(AppSetting(key=KEY, value=sw))
    return sw


def gate(sw: dict, fqdns: list[str]) -> str | None:
    """Why a run with these subdomains may not write DNS now (None = allowed)."""
    m = mode(sw)
    if m == "off":
        return "Ghi DNS thật đang TẮT — anh bật ở Cài đặt › Ghi DNS thật khi duyệt chạy thử"
    if m == "trial" and sorted(set(fqdns)) != [sw["trial_fqdn"]]:
        return f"Đang chạy thử: chỉ được chạy đúng 1 miền thử {sw['trial_fqdn']} — chạy hàng loạt sau khi miền thử thành công"
    return None


def mark_trial(s: Session, fqdn: str, job_id: int) -> bool:
    sw = get_switch(s)
    if mode(sw) == "trial" and fqdn == sw["trial_fqdn"]:
        sw.update(trial_passed=True, trial_job=job_id, changed_at=datetime.now(timezone.utc).isoformat())
        s.merge(AppSetting(key=KEY, value=sw))
        return True
    return False


def _check_one(it: dict, nick: Nick, cache: dict, log: list) -> dict:
    """Read-only checks for one subdomain. Returns it + {action: add|exists|refuse, reason, details}."""
    root, label, fqdn, ip = it["root"], it["label"], it["fqdn"], nick.ip
    out = {**it, "nick": nick.name, "ip": ip, "action": "refuse", "checks": []}
    ok = lambda m: out["checks"].append(m)  # noqa: E731

    def say(msg, level="info"):
        log.append({"fqdn": fqdn, "level": level, "message": msg})

    try:
        cp = CPanel(nick.id, nick.cpanel_host)
        key = ("cp", root)
        if key not in cache:
            cache[key] = cp.creation_mode(root)
        how = cache[key]
        host_ip = how["ip"]
        out["hosting_ip"], out["host_mode"] = host_ip, how["mode"]
        where = root if how["mode"] == "subdomain" else f"miền chính {how['main']}"
        if host_ip and host_ip != ip:
            out["reason"] = f"IP hosting của {where} trên cPanel là {host_ip}, khác IP cấu hình cho {nick.name} ({ip}) — sửa cấu hình trước"
            return out
        if how["mode"] == "subdomain":
            ok(f"cPanel: {root} có trên tài khoản" + (f", IP {host_ip}" if host_ip else ", cPanel không báo IP") + " → tạo subdomain")
        else:
            ok(f"cPanel: {root} không nằm trên tài khoản → tạo addon domain trên {how['main']}" + (f" (IP {host_ip})" if host_ip else ""))
        if cp.subdomain(fqdn) or (how["mode"] == "addon" and cp.addon(fqdn)):
            out["reason"] = f"{fqdn} đã có trên cPanel — không tạo lại"
            return out
        if how["mode"] == "addon" and cp.subdomain(f"{fqdn}.{how['main']}"):
            out["reason"] = f"Đã có subdomain {fqdn}.{how['main']} — addon sẽ dùng lại thư mục cũ, không tạo"
            return out

        key = ("inet", nick.id, root)
        if key not in cache:
            api = Inet(nick.id, log=lambda m, level="info": say(m, level))
            d = api.find_domain(root)
            info = {"domain": d}
            if d:
                info["ns"] = api.nameservers(int(d["id"]))
                info["provider"] = dns_provider(info["ns"])
                if info["provider"] == "inet":
                    info["records"] = api.records(int(d["id"]))
            cache[key] = info
        info = cache[key]
        if not info["domain"]:
            out["reason"] = f"{root} không thuộc tài khoản iNET của {nick.name} — không dùng khoá của nick khác"
            return out
        out["domain_id"] = int(info["domain"]["id"])
        out["nameservers"] = sorted(info["ns"])
        out["dns_provider"] = info["provider"]
        if info["provider"] != "inet":
            out["reason"] = _other_provider(cp, root, info)
            return out
        ok(f"iNET: {root} thuộc tài khoản {nick.name} (ID {out['domain_id']}), nameserver {', '.join(out['nameservers'])}")
        same = [r for r in info["records"] if record_label(r.get("name"), root) == label]
        out["existing"] = [{"id": r.get("id"), "type": r.get("type"), "data": r.get("data")} for r in same]
        if any((r.get("type") or "").upper() == "A" and (r.get("data") or "").strip().rstrip(".") == ip for r in same):
            out["action"] = "exists"
            ok(f"Bản ghi {label} A {ip} đã có — không gửi lại")
        elif same:
            out["reason"] = f"{fqdn} đã có bản ghi " + ", ".join(f"{r.get('type')} {r.get('data')}" for r in same) + " — không ghi đè/sửa/xoá"
            return out
        else:
            out["action"] = "add"
            ok(f"Chưa có bản ghi {label} — sẽ thêm 1 bản ghi A {ip} (ACTION_ADD)")
        doh = net.resolve_a(fqdn)
        out["public_dns"] = doh
        if doh and set(doh) != {ip}:
            out["action"], out["reason"] = "refuse", f"DNS công khai của {fqdn} đang trỏ {', '.join(doh)} — không ghi đè"
            return out
        ok("DNS công khai: " + (", ".join(doh) if doh else "chưa có bản ghi"))
    except IntegrationError as e:
        out["action"], out["reason"] = "refuse", str(e)
    return out


def _other_provider(cp: CPanel, root: str, info: dict) -> str:
    ns = ", ".join(sorted(info["ns"])) or "không rõ"
    if info["provider"] == "cloudflare":
        return f"{root} dùng DNS Cloudflare ({ns}) — không gọi API iNET; chưa cấu hình API Cloudflare"
    try:
        auth = cp.has_local_authority(root)
    except IntegrationError:
        auth = {}
    if auth.get("local_authority") == 1:
        return (f"{root} dùng DNS của hosting cPanel ({ns}) — không gọi API iNET. "
                "Ghi qua cPanel DNS::mass_edit_zone có trong tài liệu nhưng chưa triển khai")
    return f"{root} dùng nameserver {ns} (không phải iNET, không phải hosting cPanel) — không gọi API iNET"


def preview(s: Session, items: list[dict]) -> dict:
    from .service import validate_items

    ok_items, refused = validate_items(s, items)
    sw = get_switch(s)
    cache, log, rows = {}, [], []
    for it in ok_items:
        rows.append(_check_one(it, s.get(Nick, it["nick_id"]), cache, log))
    for row, why in refused.items():
        rows.append({"row": row, "action": "refuse", "reason": why})
    runnable = [r for r in rows if r["action"] in ("add", "exists")]
    why = gate(sw, [r["fqdn"] for r in runnable]) if runnable else "Không có dòng nào chạy được"
    token = None
    if runnable and not why:
        token = secrets.token_urlsafe(16)
        keep = ("row", "company", "root", "label", "fqdn", "nick_id", "ip", "domain_id", "action")
        s.merge(AppSetting(key=f"dns_preview:{token}", value={
            "at": datetime.now(timezone.utc).isoformat(), "mode": mode(sw), "items": [{k: r.get(k) for k in keep} for r in runnable]}))
    return {"mode": mode(sw), "trial_fqdn": sw["trial_fqdn"], "blocked": why, "token": token, "rows": rows, "api_log": log}


def take_plan(s: Session, token: str) -> list[dict]:
    row = s.get(AppSetting, f"dns_preview:{token}") if token else None
    if not row:
        raise ValueError("Chưa xem trước, hoặc bản xem trước đã dùng — kiểm tra lại trước khi chạy")
    s.delete(row)
    at = datetime.fromisoformat(row.value["at"])
    if datetime.now(timezone.utc) - at > timedelta(minutes=PLAN_MINUTES):
        raise ValueError(f"Bản xem trước đã quá {PLAN_MINUTES} phút — kiểm tra lại trước khi chạy")
    return row.value["items"]
