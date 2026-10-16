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
from ...integrations.errors import Conflict, NotAvailable, Permanent, Transient
from ...integrations.google import Sheets
from ...integrations.inet import Inet
from ...jobs import JobContext, enqueue, handler
from ...models import Job, Nick, RootDomain, SheetWrite

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


def set_selected(s: Session, names: list[str], on: bool) -> dict:
    changed, refused = [], {}
    for name in names:
        r = s.get(RootDomain, name)
        if not r:
            refused[name] = "Không có trong danh sách"
            continue
        if on and (why := root_issue(r, s.get(Nick, r.nick_id))):
            refused[name] = why
        elif not on and root_busy(s, name):
            refused[name] = "Đang có tác vụ trên miền này — bỏ chọn sau khi xong"
        else:
            r.selected = on
            changed.append(name)
    return {"changed": changed, "refused": refused}


def slug(company: str) -> str:
    """Legacy _slug_for_subdomain: drop legal suffixes and symbols. (Naming rule still to be confirmed by the owner.)"""
    return re.sub(r"[^a-z0-9]", "", LEGAL.sub("", company.lower()))


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
            "tab": settings().sheet_tab}


def enqueue_rows(s: Session, items: list[dict]) -> dict:
    """items: [{row, company, root, label}] — validated again here; the UI is never trusted."""
    queued, refused = [], {}
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
        job, created = enqueue(s, "domain_create", f"domain:{fqdn}",
                               {"row": it["row"], "company": it.get("company", ""), "root": root, "label": label, "fqdn": fqdn, "nick_id": r.nick_id},
                               resource=f"nick:{r.nick_id}")
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
        if not cp.domain_data(p["root"]):
            raise Permanent(f"Miền gốc {p['root']} chưa có trên tài khoản cPanel của {nick.name} — thêm miền gốc vào hosting trước")
        if cp.subdomain(fqdn):
            raise Permanent(f"{fqdn} đã tồn tại trên cPanel — không tạo lại. Đổi tên hoặc miền gốc")
        existing = net.resolve_a(fqdn)
        if existing:
            raise Permanent(f"{fqdn} đã có bản ghi A ({', '.join(existing)}) — không ghi đè")
        ctx.log("Không trùng: Sheet, cPanel, DNS", "ok")

        ctx.step("Tạo bản ghi A")
        if root.dns_host == "inet":
            Inet(nick.id).create_a_record(p["root"], p["label"], nick.ip)  # blocked until iNET documents the body
        else:
            raise NotAvailable("DNS cPanel", "chưa triển khai DNS::mass_edit_zone (không miền gốc nào đang dùng NS cPanel)")
        ctx.checkpoint(dns_created=True)
        ctx.log(f"Tạo bản ghi A {fqdn} → {nick.ip}", "ok")

    if not st.get("host_created"):
        ctx.step("Tạo miền trên cPanel")
        _gate(s, p["root"])
        cp = CPanel(nick.id, nick.cpanel_host)
        cp.add_subdomain(p["label"], p["root"], f"public_html/{fqdn}")
        ctx.checkpoint(host_created=True)
        ctx.log(f"cPanel: đã tạo {fqdn}", "ok")

    ctx.step("Xác minh DNS trỏ đúng IP")
    ips = net.resolve_a(fqdn)
    if nick.ip not in ips:
        raise Transient(f"DNS {fqdn} chưa trỏ về {nick.ip} (đang: {', '.join(ips) or 'chưa có'}) — chờ lan truyền", 300)
    ctx.log(f"DNS {fqdn} → {nick.ip}", "ok")

    ctx.step("Đọc lại ô B rồi ghi")
    live = sheets.read_cell(cell)
    if live.strip():
        ctx.checkpoint(outcome="conflict", orphan={"fqdn": fqdn, "found_b": live})
        raise Conflict(f"Ô {cell} đã có “{live}” khi ghi — không ghi đè. Miền {fqdn} đã tạo, lưu vào “Tài nguyên chưa gắn”")
    sheets.write_cell(cell, fqdn)
    s.add(SheetWrite(tab=sheets.s.sheet_tab, range=cell, old_value="", new_value=fqdn, job_id=ctx.job.id))
    ctx.checkpoint(written_b=fqdn)
    ctx.log(f"Ghi {cell} = {fqdn} · cột C giữ nguyên", "ok")
