"""Domain Manager: rows with an empty B → subdomain under a ticked root domain → verify → write B.

Rules: only ticked, usable roots are ever used (checked at enqueue AND before every creating step);
B is written only after A record + cPanel subdomain + DNS points to the hosting IP + B still empty at write time.
C is never touched. Everything over official APIs; no browser automation.
"""
import json
import re
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import API_ROOT, settings
from ...integrations import net
from ...integrations.cpanel import CPanel
from ...integrations.errors import Conflict, NotAvailable, Permanent, Transient, wait_or_fail
from ...integrations.google import Sheets
from ...integrations.inet import Inet
from ...jobs import JobContext, enqueue, handler
from . import dns_plan
from ...models import AppSetting, Job, Nick, RootDomain, SheetWrite

DNS_WAIT_HOURS = 12  # a new record normally shows within minutes; past this something is wrong
LABEL_RX = re.compile(r"^(?!-)[a-z0-9-]{1,63}(?<!-)$")
LEGAL = re.compile(r"\b(llc|inc|pllc|co|corp|ltd)\b\.?")


def seed(s: Session):
    """Load nick + root data once (non-secret config). Never overwrites the owner's ticks."""
    path = settings().nicks_file or str(API_ROOT / "config" / "nicks.example.json")
    data = json.loads(open(path, encoding="utf-8").read())
    for n in data["nicks"]:
        if not s.get(Nick, n["id"]):
            s.add(Nick(id=n["id"], name=n["name"], ip=n["ip"], hosting=n.get("hosting"), cpanel_host=n["cpanel_host"]))
        s.flush()
        for r in n["roots"]:
            name, dns, exp, apex = r[:4]
            if not s.get(RootDomain, name):
                s.add(RootDomain(name=name, nick_id=n["id"], dns_host=dns, expires=date.fromisoformat(exp),
                                 apex_on_hosting=apex, suspended=len(r) > 4 and r[4] == "suspended", selected=False))


def root_issue(r: RootDomain, nick: Nick) -> str | None:
    if r.suspended:
        return "Miền đang tạm ngưng"
    if r.expires and r.expires < date.today():
        return "Miền đã hết hạn"
    if r.dns_host == "other":
        return "DNS ở nhà cung cấp khác (Cloudflare) — API iNET không ghi được"
    if r.dns_host == "unknown":
        return "Chưa xác định nameserver"
    if not nick.enabled:
        return f"Nick {nick.name} đang tắt"
    return None


def root_busy(s: Session, root: str) -> bool:
    for job in s.scalars(select(Job).where(Job.kind == "domain_create", Job.status.in_(("queued", "running", "failed", "blocked")))):
        if job.payload.get("root") == root and (job.status in ("queued", "running") or job.state.get("dns_created") or job.state.get("host_created")):
            return True
    return False


def cpanel_domains(s: Session, nick_id: str) -> set[str] | None:
    """Domains that the last read-only check found on the nick's cPanel account; None = never checked."""
    row = s.get(AppSetting, f"cpanel_domains:{nick_id}")
    return set(row.value.get("domains", [])) if row else None


def check_nick(s: Session, nick_id: str) -> dict:
    """Read-only: which roots exist on the cPanel account and in the nick's iNET account."""
    from datetime import datetime, timezone

    from ...integrations.errors import IntegrationError

    nick = s.get(Nick, nick_id)
    if not nick:
        raise Permanent("Không có nick này")
    out: dict = {"nick": nick.name}
    try:
        d = CPanel(nick.id, nick.cpanel_host).list_domains()
        names = sorted({x.lower() for x in [d.get("main_domain") or ""] + (d.get("addon_domains") or []) + (d.get("parked_domains") or []) if x})
        s.merge(AppSetting(key=f"cpanel_domains:{nick.id}", value={"domains": names, "at": datetime.now(timezone.utc).isoformat()}))
        roots = [r.name for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == nick.id))]
        out["cpanel"] = {"ok": True, "on_hosting": [r for r in roots if r in names], "missing": [r for r in roots if r not in names],
                         "subdomains": len(d.get("sub_domains") or [])}
        try:
            out["cpanel"]["version"] = CPanel(nick.id, nick.cpanel_host).version()
        except IntegrationError as e:
            out["cpanel"]["version"] = f"không đọc được ({e})"
    except IntegrationError as e:
        out["cpanel"] = {"ok": False, "error": str(e)}
    try:
        inet_names = sorted({(d.get("name") or "").lower() for d in Inet(nick.id).list_domains() if d.get("name")})
        s.merge(AppSetting(key=f"inet_domains:{nick.id}", value={"domains": inet_names, "at": datetime.now(timezone.utc).isoformat()}))
        roots = [r.name for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == nick.id))]
        missing = [r for r in roots if r not in inet_names]
        out["inet"] = {"ok": True, "domains": len(inet_names), "missing": missing,
                       "note": f"{len(inet_names)} miền trong tài khoản" + (f", không thấy {', '.join(missing)}" if missing else ", có đủ các miền gốc")}
    except IntegrationError as e:
        out["inet"] = {"ok": False, "error": str(e)}
    return out


def set_selected(s: Session, names: list[str], on: bool) -> dict:
    changed, refused = [], {}
    for name in names:
        r = s.get(RootDomain, name)
        if not r:
            refused[name] = "Không có trong danh sách"
            continue
        if on and (why := root_issue(r, s.get(Nick, r.nick_id))):
            refused[name] = why
        elif on and (known := cpanel_domains(s, r.nick_id)) is not None and name not in known:
            refused[name] = "Miền gốc chưa có trên tài khoản cPanel của nick (kiểm tra hosting gần nhất) — thêm vào hosting trước"
        elif not on and root_busy(s, name):
            refused[name] = "Đang có tác vụ trên miền này — bỏ chọn sau khi xong"
        else:
            r.selected = on
            changed.append(name)
    return {"changed": changed, "refused": refused}


BR_SUFFIX = re.compile(r"[\s,.-]+(ltda|eireli|epp|me|s/?a)\.?\s*$")  # Brazilian legal forms, only at the end


def slug(company: str) -> str:
    """Legacy _slug_for_subdomain: drop legal suffixes and symbols; accents are folded ("ç" → "c"), not dropped.
    Same rule as subdomainSlug() in the web app. (Naming rule still to be confirmed by the owner.)"""
    from ..pdf.fields import strip_accents

    name = BR_SUFFIX.sub("", strip_accents(company.lower()))
    return re.sub(r"[^a-z0-9]", "", LEGAL.sub("", name))


def scan(s: Session) -> dict:
    rows = Sheets().read_rows()
    out, excluded = [], []
    for r in rows:
        c = r.cells
        if c["B"].strip():
            continue
        if not c["A"].strip():
            excluded.append({"row": r.row, "reason": "Thiếu tên doanh nghiệp (A)"})
            continue
        flags = []
        if not c["K"].strip():
            flags.append("Chưa có link K")
        if not c["E"].strip():
            flags.append("Thiếu cột E")
        out.append({"row": r.row, "A": c["A"], "D": c["D"], "E": c["E"], "F": c["F"], "G": c["G"], "H": c["H"], "I": c["I"],
                    "J": c["J"], "K": c["K"], "flags": flags, "label": slug(c["A"])})
    existing_b = sorted({r.cells["B"].strip().lower() for r in rows if r.cells["B"].strip()})
    return {"total": len(rows), "with_b": len(existing_b), "rows": out, "excluded": excluded, "existing_b": existing_b,
            "tab": Sheets().tab}


def validate_items(s: Session, items: list[dict]) -> tuple[list[dict], dict]:
    """items: [{row, company, root, label, …}] — the UI is never trusted: only ticked, usable roots, valid labels."""
    ok, refused = [], {}
    taken = set()
    for it in items:
        label, root = (it.get("label") or "").lower(), it.get("root") or ""
        r = s.get(RootDomain, root)
        why = None
        if not r:
            why = "Chưa gán miền gốc"
        elif not r.selected:
            why = f"Miền gốc {root} chưa được tích chọn"
        else:
            why = root_issue(r, s.get(Nick, r.nick_id))
        if not why and not LABEL_RX.match(label):
            why = "Tên miền phụ chỉ gồm a–z, 0–9, “-”, tối đa 63 ký tự"
        fqdn = f"{label}.{root}"
        if not why and fqdn in taken:
            why = "Trùng với dòng khác trong lượt này"
        if why:
            refused[it.get("row")] = why
            continue
        taken.add(fqdn)
        ok.append({**it, "row": it["row"], "company": it.get("company", ""), "root": root, "label": label, "fqdn": fqdn, "nick_id": r.nick_id})
    return ok, refused


def enqueue_rows(s: Session, items: list[dict]) -> dict:
    """One job per subdomain. Normally fed by a confirmed preview plan (dns_plan.take_plan)."""
    ok, refused = validate_items(s, items)
    queued = []
    for it in ok:
        payload = {k: it[k] for k in ("row", "company", "root", "label", "fqdn", "nick_id")}
        if it.get("domain_id") is not None:
            payload["domain_id"] = it["domain_id"]  # iNET ID seen in the preview — must still match when writing
        job, created = enqueue(s, "domain_create", f"domain:{it['fqdn']}", payload, resource=f"nick:{it['nick_id']}")
        queued.append({"row": it["row"], "job_id": job.id, "created": created})
    return {"queued": queued, "refused": refused}


def _gate(s: Session, root: str):
    r = s.get(RootDomain, root)
    if not r or not r.selected:
        raise Permanent(f"Dừng trước khi tạo: miền gốc {root} không còn được tích chọn. B giữ trống.")
    if why := root_issue(r, s.get(Nick, r.nick_id)):
        raise Permanent(f"Dừng trước khi tạo: {root} — {why}. B giữ trống.")
    return r


@handler("domain_create")
def _create(ctx: JobContext):
    s, p, st = ctx.session, ctx.job.payload, ctx.state
    nick = s.get(Nick, p["nick_id"])
    fqdn, cell = p["fqdn"], f"B{p['row']}"
    sheets = Sheets()

    if not st.get("dns_created"):
        ctx.step("Kiểm tra trước khi tạo")
        root = _gate(s, p["root"])
        if sheets.read_cell(cell).strip():
            raise Conflict(f"Ô {cell} đã có dữ liệu — không tạo miền, không ghi đè")
        cp = CPanel(nick.id, nick.cpanel_host)
        dd = cp.domain_data(p["root"])
        if not dd:
            raise Permanent(f"Miền gốc {p['root']} chưa có trên tài khoản cPanel của {nick.name} — thêm miền gốc vào hosting trước")
        if dd.get("ip") and dd["ip"] != nick.ip:
            raise Permanent(f"IP hosting của {p['root']} trên cPanel ({dd['ip']}) khác IP của {nick.name} ({nick.ip}) — dừng")
        if cp.subdomain(fqdn):
            raise Permanent(f"{fqdn} đã tồn tại trên cPanel — không tạo lại. Đổi tên hoặc miền gốc")
        existing = net.resolve_a(fqdn)
        if existing and set(existing) != {nick.ip}:
            raise Permanent(f"{fqdn} đã có bản ghi A ({', '.join(existing)}) — không ghi đè")
        if existing:  # e.g. added by an earlier attempt that stopped before saving its progress
            ctx.log(f"DNS công khai: {fqdn} đã trỏ {nick.ip} — iNET sẽ được kiểm tra, chỉ thêm nếu chưa có", "warn")
        ctx.log(f"Không trùng: Sheet, cPanel, DNS · {fqdn} → {nick.name} ({nick.ip})", "ok")

        ctx.step("Tạo bản ghi A")
        if why := dns_plan.gate(dns_plan.get_switch(s), [fqdn]):
            raise NotAvailable("Ghi DNS thật", why)
        if root.dns_host != "inet":
            raise NotAvailable("DNS", f"{p['root']} không dùng DNS iNET — chưa có API nhà cung cấp DNS này")
        rec = Inet(nick.id, log=ctx.log).create_a_record(p["root"], p["label"], nick.ip, expect_domain_id=p.get("domain_id"))
        ctx.checkpoint(dns_created=True, dns_record=rec)
        ctx.log(f"Bản ghi A {fqdn} → {nick.ip}: " + ("đã có sẵn, không gửi lại" if rec["result"] == "exists" else "đã thêm trên iNET"), "ok")

    if not st.get("host_created"):
        ctx.step("Tạo miền trên cPanel")
        _gate(s, p["root"])
        cp = CPanel(nick.id, nick.cpanel_host)
        if cp.subdomain(fqdn):  # created by an earlier attempt whose answer was lost (before it, the pre-check found none)
            ctx.log(f"cPanel: {fqdn} đã có từ lượt trước → không tạo lại", "warn")
        else:
            cp.add_subdomain(p["label"], p["root"], f"public_html/{fqdn}")
            ctx.log(f"cPanel: đã tạo {fqdn}", "ok")
        ctx.checkpoint(host_created=True)

    ctx.step("Xác minh DNS trỏ đúng IP")
    ips = net.resolve_a(fqdn)
    if nick.ip not in ips:
        wait_or_fail(st, "dns_wait_since", DNS_WAIT_HOURS, f"DNS {fqdn} chưa trỏ về {nick.ip} (đang: {', '.join(ips) or 'chưa có'})", 300)
    ctx.log(f"DNS {fqdn} → {nick.ip}", "ok")

    ctx.step("Đọc lại ô B rồi ghi")
    company_now = sheets.read_cell(f"A{p['row']}").strip()
    if p.get("company") and company_now.casefold() != p["company"].strip().casefold():
        ctx.checkpoint(outcome="conflict", orphan={"fqdn": fqdn, "row_now": company_now})
        raise Conflict(f"Dòng {p['row']} giờ là “{company_now}”, không còn là “{p['company']}” (Sheet đã đổi thứ tự?) — "
                       f"không ghi B. Miền {fqdn} đã tạo, lưu vào “Tài nguyên chưa gắn”")
    live = sheets.read_cell(cell)
    if live.strip():
        ctx.checkpoint(outcome="conflict", orphan={"fqdn": fqdn, "found_b": live})
        raise Conflict(f"Ô {cell} đã có “{live}” khi ghi — không ghi đè. Miền {fqdn} đã tạo, lưu vào “Tài nguyên chưa gắn”")
    sheets.write_cell(cell, fqdn)
    s.add(SheetWrite(tab=sheets.tab, range=cell, old_value="", new_value=fqdn, job_id=ctx.job.id))
    ctx.checkpoint(written_b=fqdn)
    ctx.log(f"Ghi {cell} = {fqdn} · cột C giữ nguyên", "ok")
    if dns_plan.mark_trial(s, fqdn, ctx.job.id):
        ctx.log(f"Chạy thử thành công trên {fqdn} — từ giờ được chạy hàng loạt (vẫn phải xem trước và xác nhận)", "ok")
