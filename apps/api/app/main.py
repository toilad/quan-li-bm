"""Quản Lí BM API (FastAPI). Run: uvicorn app.main:app --port 8000"""
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from wg_core import jobs, registry
from wg_core.config import settings
from wg_core.runtime_config import get as cfg
from wg_core.db import session_scope
from wg_core.integrations.errors import Conflict, NotAvailable, NotConfigured, Permanent, Transient
from wg_core.models import Job, JobLog, Nick, PdfDocument, RootDomain
from wg_core.modules.domains import service as domains
from wg_core.modules.domains import dns_plan
from wg_core.modules.pdf import service as pdf
from wg_core.modules.pdf.fields import FIELD_KEYS, validate
from wg_core.modules.websites import service as websites
from wg_core.modules.websites.templates import TEMPLATES
from wg_core.status import integration_status

@asynccontextmanager
async def lifespan(_: FastAPI):
    registry.setup()  # tables + nick/root seed (never touches the owner’s ticks)
    yield


app = FastAPI(title="Quản Lí BM API", version="0.1", lifespan=lifespan)
from app.auth_api import AuthMiddleware, allowed_origins  # noqa: E402
from app.auth_api import router as auth_router  # noqa: E402

# Order matters: CORS is added last so it is the outermost layer (401/403 answers still carry CORS headers).
app.add_middleware(AuthMiddleware)
app.add_middleware(CORSMiddleware, allow_origins=sorted(allowed_origins()), allow_credentials=True, allow_methods=["*"], allow_headers=["*"])
app.include_router(auth_router)

from app.settings_api import router as settings_router  # noqa: E402

app.include_router(settings_router)


def db():
    with session_scope() as s:
        yield s


@app.exception_handler(NotConfigured)
def _nc(_: Request, e: NotConfigured):
    return JSONResponse(status_code=503, content={"status": "not_configured", "service": e.service, "missing": e.missing, "message": str(e)})


@app.exception_handler(NotAvailable)
def _na(_: Request, e: NotAvailable):
    return JSONResponse(status_code=501, content={"status": "not_available", "service": e.service, "message": str(e)})


@app.exception_handler(Permanent)
def _pe(_: Request, e: Permanent):
    return JSONResponse(status_code=422, content={"status": "error", "message": str(e)})


@app.exception_handler(Transient)
def _tr(_: Request, e: Transient):
    return JSONResponse(status_code=502, content={"status": "retry", "message": str(e)})


@app.exception_handler(Conflict)
def _cf(_: Request, e: Conflict):
    return JSONResponse(status_code=409, content={"status": "conflict", "message": str(e)})


# ───────── status / jobs ─────────

@app.get("/api/health")
def health(s: Session = Depends(db)):
    s.execute(select(1))
    return {"ok": True}


@app.get("/api/status")
def status(s: Session = Depends(db)):
    return integration_status(s)


@app.get("/api/ai/check")
def ai_check():
    """Before any real AI call: confirm the configured model exists for this key (Models API, no tokens used)."""
    from wg_core.integrations import ai

    return ai.check_model()


@app.get("/api/backups")
def backups():
    """Real backup files (scripts/backup.py). Restore drills are not automated yet."""
    from datetime import datetime

    from wg_core.config import API_ROOT

    dumps = sorted((API_ROOT / "backups").glob("*.dump"), key=lambda p: p.stat().st_mtime, reverse=True)
    latest = datetime.fromtimestamp(dumps[0].stat().st_mtime).isoformat(timespec="minutes") if dumps else None
    return {"count": len(dumps), "latest": latest, "restore_test": None}


def job_out(j: Job, logs: list[JobLog] | None = None) -> dict:
    out = {"id": j.id, "kind": j.kind, "status": j.status, "step": j.step, "attempts": j.attempts, "error": j.last_error,
           "payload": j.payload, "state": {k: v for k, v in (j.state or {}).items() if k != "copy"},
           "run_after": j.run_after.isoformat() if j.run_after else None, "updated_at": j.updated_at.isoformat() if j.updated_at else None}
    if logs is not None:
        out["logs"] = [{"at": l.at.isoformat(), "level": l.level, "message": l.message} for l in logs]
    return out


@app.get("/api/jobs")
def list_jobs(kind: str | None = None, s: Session = Depends(db)):
    q = select(Job).order_by(Job.id.desc()).limit(500)
    if kind:
        q = q.where(Job.kind == kind)
    js = list(s.scalars(q))
    logs = {}
    for l in s.scalars(select(JobLog).where(JobLog.job_id.in_([j.id for j in js])).order_by(JobLog.id)) if js else []:
        logs.setdefault(l.job_id, []).append(l)
    return [job_out(j, logs.get(j.id, [])) for j in js]


class PauseBody(BaseModel):
    kind: str = "*"  # pdf_save | pdf_ai_read | domain_create | web_build | selftest | "*"
    on: bool


@app.get("/api/queue")
def queue(s: Session = Depends(db)):
    from sqlalchemy import func

    counts = {f"{k}:{st}": n for k, st, n in s.execute(select(Job.kind, Job.status, func.count()).group_by(Job.kind, Job.status))}
    return {"paused": sorted(jobs.paused_kinds(s)), "counts": counts}


@app.post("/api/queue/pause")
def pause(body: PauseBody, s: Session = Depends(db)):
    return {"paused": sorted(jobs.set_paused(s, body.kind, body.on))}


class SelftestBody(BaseModel):
    count: int = 3
    steps: int = 3
    sleep: float = 0.5
    fail_once_at: int | None = 2
    key: str = "demo"


@app.post("/api/queue/selftest")
def selftest(body: SelftestBody, s: Session = Depends(db)):
    """Fake jobs (no external call) to check dedupe / pause / retry on the running worker."""
    out = []
    for i in range(body.count):
        job, created = jobs.enqueue(s, "selftest", f"selftest:{body.key}:{i}", body.model_dump(exclude={"count", "key"}), resource="selftest")
        out.append({"job_id": job.id, "created": created})
    return out


@app.post("/api/jobs/{job_id}/retry")
def retry_job(job_id: int, s: Session = Depends(db)):
    j = jobs.retry(s, job_id)
    if not j:
        raise HTTPException(404)
    return job_out(j)


# ───────── PDF ─────────

def doc_out(d: PdfDocument) -> dict:
    issues = validate(d.fields, d.doc_type) if d.fields else {}
    return {"id": d.id, "name": d.original_name, "md5": d.md5, "size": d.size, "pages": d.pages, "has_text": d.has_text,
            "doc_type": d.doc_type, "confidence": d.detection_confidence, "reason": d.detection_reason, "fields": d.fields,
            "extra": d.extra, "industry": d.industry, "status": d.status, "error": d.error, "issues": issues,
            "drive_file_id": d.drive_file_id, "drive_link": d.drive_link, "sheet_row": d.sheet_row}


@app.get("/api/pdf")
def list_pdf(s: Session = Depends(db)):
    return [doc_out(d) for d in s.scalars(select(PdfDocument).order_by(PdfDocument.id.desc()))]


@app.post("/api/pdf/upload")
async def upload_pdf(files: list[UploadFile] = File(...), s: Session = Depends(db)):
    out = []
    for f in files:
        data = await f.read()
        try:
            doc, new = pdf.ingest(s, f.filename or "file.pdf", data)
            out.append({**doc_out(doc), "duplicate": not new})
        except Permanent as e:
            out.append({"name": f.filename, "status": "rejected", "error": str(e)})
    return out


@app.get("/api/pdf/{doc_id}/file")
def pdf_file(doc_id: int, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    return FileResponse(pdf.storage_path(d.md5), media_type="application/pdf")


def _live_save(s: Session, d: PdfDocument) -> bool:
    return bool(s.scalar(select(Job.id).where(Job.idem_key == f"pdf:{d.md5}", Job.status.in_(("queued", "running")))))


class PdfEdit(BaseModel):
    fields: dict[str, str] | None = None
    doc_type: str | None = None
    industry: str | None = None  # owner’s manual industry category
    # owner confirms the email printed on the PDF is the business's own official contact
    # (comprovantes often carry the accountant's address); only then may a website show it
    email_verified: bool | None = None


@app.patch("/api/pdf/{doc_id}")
def edit_pdf(doc_id: int, body: PdfEdit, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    if body.email_verified is not None:
        # not part of the Sheet row, so it can still be set after saving
        if body.email_verified and not (d.extra or {}).get("email"):
            raise HTTPException(422, "Phôi không có email để xác minh")
        d.extra = {**(d.extra or {}), "email_verified": body.email_verified}
        if body.fields is None and body.doc_type is None and body.industry is None:
            return doc_out(d)
    if d.status == "saved" or _live_save(s, d):
        raise HTTPException(409, "Đã lưu / đang lưu — không sửa")
    if d.status == "queued":  # last save stopped (blocked/failed): editable again
        d.status = "review"
    if body.doc_type and body.doc_type != d.doc_type:
        if body.doc_type not in ("wy", "ca", "br"):
            raise HTTPException(422, "Loại phôi không hợp lệ")
        pdf.extract_into(d, pdf.storage_path(d.md5).read_bytes(), forced_type=body.doc_type)
    if body.fields:
        f = dict(d.fields)
        for k, v in body.fields.items():
            if k in FIELD_KEYS:
                f[k] = {"value": v.strip(), "source": "manual" if v.strip() else "missing"}
        d.fields = f
    if body.industry:
        d.industry = {**(d.industry or {}), "category": body.industry, "source": "manual"}
    return doc_out(d)


@app.post("/api/pdf/{doc_id}/ai-read")
def ai_read(doc_id: int, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    if not cfg("ANTHROPIC_API_KEY"):
        raise NotConfigured("AI (Anthropic)", ["ANTHROPIC_API_KEY"])
    job, _ = pdf.request_ai_read(s, d)
    return job_out(job)


class SaveBody(BaseModel):
    confirm_missing: bool = False
    critical_checked: bool = False


@app.post("/api/pdf/{doc_id}/save")
def save_pdf(doc_id: int, body: SaveBody, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    if d.status == "saved":
        raise HTTPException(409, "Đã lưu")
    if _live_save(s, d):
        raise HTTPException(409, "Đang lưu — chờ tác vụ hiện tại xong")
    reasons = pdf.save_check(d, body.confirm_missing, body.critical_checked)
    if reasons:
        raise HTTPException(422, {"message": "Chưa lưu được", "reasons": reasons})
    job, _ = pdf.request_save(s, d)
    return job_out(job)


# ───────── Domains ─────────

@app.get("/api/domains/roots")
def roots(s: Session = Depends(db)):
    out = []
    for n in s.scalars(select(Nick).order_by(Nick.id)):
        rs = []
        on_cp = domains.cpanel_domains(s, n.id)
        for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == n.id).order_by(RootDomain.name)):
            rs.append({"name": r.name, "dns_host": r.dns_host, "expires": r.expires.isoformat() if r.expires else None,
                       "days_left": (r.expires - date.today()).days if r.expires else None, "apex_on_hosting": r.apex_on_hosting,
                       "suspended": r.suspended, "selected": r.selected, "issue": domains.root_issue(r, n), "busy": domains.root_busy(s, r.name),
                       "on_cpanel": None if on_cp is None else r.name in on_cp})
        out.append({"id": n.id, "name": n.name, "ip": n.ip, "hosting": n.hosting, "cpanel_host": n.cpanel_host, "enabled": n.enabled, "roots": rs})
    return out


class SelectBody(BaseModel):
    names: list[str]
    on: bool


@app.post("/api/domains/roots/select")
def select_roots(body: SelectBody, s: Session = Depends(db)):
    return domains.set_selected(s, body.names, body.on)


@app.post("/api/domains/check/{nick_id}")
def check_nick(nick_id: str, s: Session = Depends(db)):
    """Read-only check of one nick: cPanel domain list + raw iNET domain list."""
    return domains.check_nick(s, nick_id)


@app.get("/api/domains/rows")
def domain_rows(s: Session = Depends(db)):
    return domains.scan(s)


class PreviewBody(BaseModel):
    items: list[dict]


@app.post("/api/domains/preview")
def domain_preview(body: PreviewBody, s: Session = Depends(db)):
    """Read-only check over the APIs of every subdomain about to be created; returns a single-use plan token."""
    if not any(r.selected for r in s.scalars(select(RootDomain))):
        raise HTTPException(422, "Chưa tích chọn miền gốc nào — không bắt đầu")
    return dns_plan.preview(s, body.items)


class RunBody(BaseModel):
    token: str


@app.post("/api/domains/run")
def domain_run(body: RunBody, s: Session = Depends(db)):
    """Runs exactly the plan the owner confirmed in the preview — nothing else."""
    try:
        items = dns_plan.take_plan(s, body.token)
    except ValueError as e:
        raise HTTPException(409, str(e)) from e
    if why := dns_plan.gate(dns_plan.get_switch(s), [i["fqdn"] for i in items]):
        raise HTTPException(409, why)
    return domains.enqueue_rows(s, items)


class DnsWriteBody(BaseModel):
    enabled: bool | None = None
    trial_fqdn: str | None = None


@app.get("/api/domains/dns-write")
def dns_write_get(s: Session = Depends(db)):
    sw = dns_plan.get_switch(s)
    return {**sw, "mode": dns_plan.mode(sw)}


@app.put("/api/domains/dns-write")
def dns_write_put(body: DnsWriteBody, s: Session = Depends(db)):
    try:
        sw = dns_plan.set_switch(s, enabled=body.enabled, trial_fqdn=body.trial_fqdn)
    except ValueError as e:
        raise HTTPException(422, str(e)) from e
    return {**sw, "mode": dns_plan.mode(sw)}


# ───────── Websites ─────────

@app.get("/api/websites/templates")
def templates():
    return [{"id": t.id, "name": t.name, "group": t.group, "primary": t.primary, "accent": t.accent, "hero": t.hero,
             "photo_keywords": list(t.photo_keywords), "industries": list(t.industries)} for t in TEMPLATES]


PREVIEW_COPY = {
    "tagline": "[Tagline — AI writes it from the Sheet facts]", "hero_subtitle": "[One or two sentences written by AI for this business]",
    "primary_cta": "Get a Quote", "intro_paragraph": "[Intro paragraph written by AI — no invented facts]",
    "about_short": "[Short about text written by AI]", "about_full": "[About page, paragraph 1]\n\n[Paragraph 2]\n\n[Paragraph 3]",
    "contact_intro": "[Contact intro written by AI]", "footer_blurb": "[Footer line written by AI]",
    "meta_description_home": "Preview", "meta_description_about": "Preview", "meta_description_contact": "Preview", "meta_description_faq": "Preview",
    "services": [{"title": f"[Service {i}]", "description": "[Description written by AI]"} for i in (1, 2, 3)],
    "why_choose_us": [{"title": f"[Reason {i}]", "description": "[Written by AI]"} for i in (1, 2, 3)],
    "faqs": [{"q": f"[Question {i}]", "a": "[Answer written by AI]"} for i in (1, 2, 3, 4, 5)],
}


TEMPLATE_IDS = {t.id for t in TEMPLATES}
PREVIEW_PHOTO_HOURS = 23  # Pixabay: cache searches 24 h, its links last 24 h; Pexels has no such limit


def _preview_photos(domain: str, template: str) -> list[dict]:
    """Same choice as the build (cached a day per domain + template, so previews cost no extra photo API requests)."""
    import hashlib
    from datetime import datetime, timedelta, timezone

    from wg_core.integrations.errors import IntegrationError
    from wg_core.models import AppSetting
    from wg_core.modules.websites.brand_render import design

    provider = websites.photos.provider_name()
    if not provider:
        return []
    key = "photo_preview:" + hashlib.sha256(f"{provider}|{template}|{domain}".encode()).hexdigest()[:40]
    with session_scope() as s:
        row = s.get(AppSetting, key)
        if row and datetime.now(timezone.utc) - datetime.fromisoformat(row.value["at"]) < timedelta(hours=PREVIEW_PHOTO_HOURS):
            return row.value["photos"]
    try:
        chosen = websites.photos.choose(domain, template, design({"domain": domain}, template))
    except IntegrationError:
        return []  # the preview still works, with the gradient panels
    with session_scope() as s:
        s.merge(AppSetting(key=key, value={"at": datetime.now(timezone.utc).isoformat(), "photos": chosen}))
    return chosen


@app.get("/api/photos/check")
def photos_check(provider: str = "pixabay"):
    """Read-only: one small search to confirm a photo key works (1 request)."""
    if provider not in websites.photos.PROVIDERS:
        raise HTTPException(404)
    r = websites.photos.PROVIDERS[provider].search("office", "landscape", per_page=3)
    return {"ok": True, "provider": provider, "found": len(r["photos"]), "remaining": r["remaining"],
            "in_use": websites.photos.provider_name() == provider}


@app.get("/api/websites/preview", response_class=HTMLResponse)
def web_preview(template: str, domain: str = "example.com", company: str = "Example Company LLC", phone: str = "",
                address: str = "", page: str = "index.html"):
    """The real template output for this domain (same renderer, design and photos the build will use), with
    placeholder copy. In this owner-only preview the photos load from Pexels / Pixabay (temporary display); the build ships them as files."""
    from wg_core.modules.websites.brand_render import render_site

    if template not in TEMPLATE_IDS:
        raise HTTPException(404)
    chosen = _preview_photos(domain.lower(), template)
    files = render_site({"company": company, "domain": domain.lower(), "phone": phone, "email": "", "address": address},
                        PREVIEW_COPY, template, photos={p["slot"]: {"src": p["src"], "alt": p["alt"]} for p in chosen},
                        credits=websites.photos.credits(chosen))
    if page not in files or not page.endswith(".html"):
        raise HTTPException(404)
    return HTMLResponse(files[page].decode("utf-8"))


@app.get("/api/websites/rows")
def web_rows(s: Session = Depends(db)):
    return websites.scan(s)


class ChoiceBody(BaseModel):
    domain: str
    template: str
    detected: str


@app.post("/api/websites/choice")
def web_choice(body: ChoiceBody, s: Session = Depends(db)):
    websites.choose(s, body.domain.lower(), body.template, body.detected)
    return {"ok": True}


@app.post("/api/websites/run")
def web_run(body: RunBody, s: Session = Depends(db)):
    return websites.enqueue_rows(s, body.items)
