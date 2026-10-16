"""SSL + Website Builder: rows with a domain in B and an empty C → build with the CHOSEN template →
deploy to the document root cPanel reports → AutoSSL → HTTPS check → write C (only if still empty)."""
from sqlalchemy import String, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from ...config import settings
from ...db import Base
from ...integrations import ai, net
from ...integrations.cpanel import CPanel
from ...integrations.errors import Conflict, Permanent, Transient
from ...integrations.google import Sheets
from ...jobs import JobContext, enqueue, handler
from ...models import Nick, RootDomain, SheetWrite
from .content_check import problems
from .legacy_render import render_site, theme_name
from .templates import BY_ID, detect


class SiteChoice(Base):
    """Template chosen for a domain (auto-detected or picked by hand). The build uses exactly this."""

    __tablename__ = "site_choices"
    domain: Mapped[str] = mapped_column(String(253), primary_key=True)
    template_id: Mapped[str] = mapped_column(String(60))
    source: Mapped[str] = mapped_column(String(10))  # auto|manual


def host_for(s: Session, domain: str):
    best = None
    for r in s.scalars(select(RootDomain)):
        if domain.endswith("." + r.name) or domain == r.name:
            if not best or len(r.name) > len(best.name):
                best = r
    return (best, s.get(Nick, best.nick_id)) if best else (None, None)


def address_of(cells: dict) -> str:
    return ", ".join(x for x in (cells["F"], cells["G"], f'{cells["H"]} {cells["I"]}'.strip()) if x)


def facts_of(cells: dict) -> dict:
    return {"Company": cells["A"], "Phone": cells["D"], "Address": address_of(cells)}


def email_of(s: Session, cells: dict) -> str:
    """The Sheet has no email column: use the email printed on the company's own PDF (Brazil comprovante), if any."""
    from ...models import PdfDocument

    j = cells["J"].strip()
    if not j:
        return ""
    for d in s.scalars(select(PdfDocument).where(PdfDocument.status == "saved")):
        if (d.fields.get("J") or {}).get("value") == j and (d.extra or {}).get("email"):
            return d.extra["email"].lower()
    return ""


def scan(s: Session) -> dict:
    rows = Sheets().read_rows()
    out = []
    for r in rows:
        c = r.cells
        if not c["B"].strip() or c["C"].strip():
            continue
        domain = c["B"].strip().lower()
        root, nick = host_for(s, domain)
        t, kw = detect(c["A"])
        choice = s.get(SiteChoice, domain)
        out.append({"row": r.row, "A": c["A"], "domain": domain, "nick": nick.name if nick else None, "ip": nick.ip if nick else None,
                    "detected": t.id, "keyword": kw, "template": choice.template_id if choice else t.id,
                    "source": choice.source if choice else "auto",
                    "issue": None if nick else "Miền ở B không thuộc miền gốc nào của các nick — không biết hosting"})
    return {"total": len(rows), "no_b": sum(1 for r in rows if not r.cells["B"].strip()),
            "has_c": sum(1 for r in rows if r.cells["C"].strip()), "rows": out}


def choose(s: Session, domain: str, template_id: str, detected: str):
    if template_id not in BY_ID:
        raise Permanent("Mẫu không tồn tại")
    c = s.get(SiteChoice, domain) or SiteChoice(domain=domain)
    c.template_id, c.source = template_id, "auto" if template_id == detected else "manual"
    s.merge(c)


def enqueue_rows(s: Session, items: list[dict]) -> dict:
    queued, refused = [], {}
    for it in items:
        domain = it["domain"].lower()
        root, nick = host_for(s, domain)
        if not nick:
            refused[it["row"]] = "Không biết hosting của miền này"
            continue
        tid = it.get("template") or (s.get(SiteChoice, domain).template_id if s.get(SiteChoice, domain) else detect(it.get("company", ""))[0].id)
        if tid not in BY_ID:
            refused[it["row"]] = "Mẫu không tồn tại"
            continue
        job, created = enqueue(s, "web_build", f"web:{domain}", {"row": it["row"], "domain": domain, "template": tid, "nick_id": nick.id},
                               resource=f"nick:{nick.id}")
        queued.append({"row": it["row"], "job_id": job.id, "created": created})
    return {"queued": queued, "refused": refused}


@handler("web_build")
def _build(ctx: JobContext):
    s, p, st = ctx.session, ctx.job.payload, ctx.state
    nick, domain, cell = s.get(Nick, p["nick_id"]), p["domain"], f"C{p['row']}"
    sheets = Sheets()
    row = next((r for r in sheets.read_rows() if r.row == p["row"]), None)
    if not row or row.cells["B"].strip().lower() != domain:
        raise Permanent(f"Dòng {p['row']}: ô B không còn là {domain} — dừng")
    if row.cells["C"].strip():
        raise Conflict(f"Ô {cell} đã có dữ liệu — không dựng lại, không ghi đè")
    template = BY_ID[p["template"]]
    facts = facts_of(row.cells)
    cp = CPanel(nick.id, nick.cpanel_host)

    if not st.get("doc_root"):
        ctx.step("Kiểm tra DNS + document root")
        ips = net.resolve_a(domain)
        if nick.ip not in ips:
            raise Permanent(f"DNS {domain} không trỏ về {nick.ip} ({', '.join(ips) or 'chưa có'}) — dừng, không upload")
        found = cp.document_root(domain)
        if not found:
            raise Permanent(f"cPanel không có {domain} trên tài khoản {nick.name} — dừng, không upload, C giữ trống")
        ctx.checkpoint(doc_root=found[0], doc_root_api=found[1])
        ctx.log(f"cPanel {found[1]}: document root {found[0]}", "ok")

    if not st.get("copy"):
        ctx.step("Tạo nội dung bằng AI")
        feedback = ""
        for attempt in range(3):
            copy = ai.write_site_copy(facts, theme_name(template.id), template.name, feedback)
            bad = problems(copy, facts)
            if not bad:
                break
            feedback = "; ".join(bad)
            ctx.log(f"Kiểm tra nội dung: {feedback} → loại, tạo lại ({attempt + 1}/2)", "warn")
        else:
            raise Permanent(f"Nội dung AI vẫn có thông tin không căn cứ sau 2 lần tạo lại: {feedback}")
        ctx.checkpoint(copy=copy)
        ctx.log("Nội dung đạt kiểm tra: không giải thưởng / khách hàng / số liệu bịa", "ok")

    if not st.get("uploaded"):
        ctx.step(f"Dựng HTML ({template.name}) + upload")
        company = {"company": row.cells["A"], "domain": domain, "phone": row.cells["D"], "email": email_of(s, row.cells),
                   "address": address_of(row.cells)}
        files = render_site(company, st["copy"], template.id)
        out = settings().data_dir / "sites" / domain
        out.mkdir(parents=True, exist_ok=True)
        for name, data in files.items():
            (out / name).write_bytes(data)
        res = cp.upload_files(st["doc_root"], files) or {}
        if res.get("failed"):
            reasons = "; ".join(f'{u.get("file")}: {u.get("reason")}' for u in res.get("uploads", []) if u.get("reason"))
            raise Permanent(f"Upload không hoàn tất (không ghi đè file có sẵn): {reasons}")
        ctx.checkpoint(uploaded=True, built_template=template.id)
        ctx.log(f"Fileman::upload_files → {st['doc_root']} · {len(files)} trang · mẫu {template.name}", "ok")

    if not st.get("https_ok"):
        ctx.step("Bật SSL (AutoSSL) + kiểm tra HTTPS")
        if not st.get("autossl_started"):
            cp.start_autossl()
            ctx.checkpoint(autossl_started=True)
            ctx.log("SSL::start_autossl_check đã gửi", "info")
        if cp.autossl_in_progress():
            raise Transient("AutoSSL đang chạy — kiểm tra lại sau", 120)
        ok, why = net.https_ok(domain, row.cells["A"])
        if not ok:
            probs = cp.autossl_problems(domain)
            raise Transient(f"HTTPS chưa chạy: {why}" + (f" · AutoSSL: {probs[0]}" if probs else ""), 900)
        ctx.checkpoint(https_ok=True)
        ctx.log(f"https://{domain}: {why}", "ok")

    ctx.step("Đọc lại ô C rồi ghi")
    live = sheets.read_cell(cell)
    if live.strip():
        ctx.checkpoint(outcome="conflict", live_not_written={"url": f"https://{domain}", "found_c": live})
        raise Conflict(f"Ô {cell} đã có “{live}” — không ghi đè. Website https://{domain} đang chạy, lưu để xử lý")
    url = f"https://{domain}"
    sheets.write_cell(cell, url)
    s.add(SheetWrite(tab=sheets.tab, range=cell, old_value="", new_value=url, job_id=ctx.job.id))
    ctx.checkpoint(written_c=url)
    ctx.log(f"Ghi {cell} = {url} · cột B giữ nguyên", "ok")
