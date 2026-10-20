"""Real DNS writes are guarded three ways (and every hosting write by wg_core/write_guard.py at the API client):

1. Switch (AppSetting "dns_write"), OFF by default, with the list of writes the owner allows. Only the owner turns it on.
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
from ... import write_guard
from ...write_guard import DEFAULT, KEY, OPS

PLAN_MINUTES = 30


def get_switch(s: Session) -> dict:
    return write_guard.load(s)


def always_b1(sw: dict) -> bool:
    return {"dns", "host"} <= set(sw.get("always") or [])


def mode(sw: dict) -> str:
    if always_b1(sw):
        return "batch"
    if not sw["enabled"]:
        return "off"
    return "batch" if sw["trial_passed"] else "trial"


def set_switch(s: Session, enabled: bool | None = None, trial_fqdn: str | None = None, ops: list[str] | None = None,
               also: list[str] | None = None, always: list[str] | None = None) -> dict:
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
            sw.update(trial_fqdn=t, trial_passed=False, trial_job=None, web_trial_passed=False, web_trial_job=None)
    if also is not None:  # extra approved names: only names the app created (B written by one of its jobs)
        from ...models import SheetWrite

        made = {w.new_value.lower() for w in s.query(SheetWrite).filter(SheetWrite.range.like("B%"))}
        if bad := [n for n in also if n.strip().lower() not in made]:
            raise ValueError(f"Chỉ thêm được tên do app đã tạo: {', '.join(bad)}")
        sw["also"] = sorted({n.strip().lower() for n in also})
    if always is not None:  # only B1's own writes can stay open for good
        if bad := sorted(set(always) - {"dns", "host"}):
            raise ValueError(f"Chỉ để mở thường trực được thao tác B1 (dns, host), không phải: {', '.join(bad)}")
        sw["always"] = [o for o in ("dns", "host") if o in always]
    if ops is not None:
        bad = sorted(set(ops) - set(OPS))
        if bad:
            raise ValueError(f"Thao tác không có: {', '.join(bad)}")
        sw["ops"] = [o for o in OPS if o in ops]
    if enabled is not None:
        if enabled and not sw["trial_passed"] and not sw["trial_fqdn"]:
            raise ValueError("Chỉ định miền thử trước khi bật ghi DNS thật")
        sw["enabled"] = enabled
        sw["locked_reason"] = None if enabled else "Anh khoá"
    sw["changed_at"] = datetime.now(timezone.utc).isoformat()
    s.merge(AppSetting(key=KEY, value=sw))
    return sw


def gate(sw: dict, fqdns: list[str]) -> str | None:
    """Why a run with these subdomains may not write DNS now (None = allowed)."""
    if always_b1(sw):  # owner, 2026-10-20: B1 always open
        return None
    m = mode(sw)
    if m == "off":
        return "Ghi thật đang KHOÁ — anh mở ở Cài đặt › Ghi thật khi duyệt chạy thử"
    if missing := [OPS[o] for o in ("dns", "host") if o not in sw["ops"]]:
        return "Anh chưa cho phép: " + ", ".join(missing) + " (Cài đặt › Ghi thật)"
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
        from .service import host_plan

        how = host_plan(cp, root, fqdn, nick)  # read-only; stops with the reason (alias, exists, folder taken, IP…)
        out["hosting_ip"], out["host_mode"] = how["ip"], how["mode"]
        ok(f"cPanel: {how['say']}" + (f", IP {how['ip']}" if how["ip"] else ", cPanel không báo IP"))

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
    if ok_items:  # one Sheet read: a company that already has a domain in another row never gets a second one
        from ...integrations.google import Sheets
        from .service import already_has_domain, domains_by_company

        sheet_rows = Sheets().read_rows()
        has, by_row = domains_by_company(sheet_rows), {r.row: r.cells for r in sheet_rows}
        for it in list(ok_items):
            cells = by_row.get(it["row"])
            if why := ("Dòng không còn trên Sheet" if cells is None else already_has_domain(has, cells)):
                refused[it["row"]] = why
                ok_items.remove(it)
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
