"""Quản Lí BM API (FastAPI). Run: uvicorn app.main:app --port 8000"""
from contextlib import asynccontextmanager
from datetime import date

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from wg_core import jobs, registry
from wg_core.config import settings
from wg_core.db import session_scope
from wg_core.integrations.errors import Conflict, NotAvailable, NotConfigured, Permanent, Transient
from wg_core.models import Job, JobLog, Nick, PdfDocument, RootDomain
from wg_core.modules.domains import service as domains
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
app.add_middleware(CORSMiddleware, allow_origins=settings().cors_origins.split(","), allow_methods=["*"], allow_headers=["*"])


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


class PdfEdit(BaseModel):
    fields: dict[str, str] | None = None
    doc_type: str | None = None


@app.patch("/api/pdf/{doc_id}")
def edit_pdf(doc_id: int, body: PdfEdit, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    if d.status in ("queued", "saved"):
        raise HTTPException(409, "Đã lưu / đang lưu — không sửa")
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
    return doc_out(d)


@app.post("/api/pdf/{doc_id}/ai-read")
def ai_read(doc_id: int, s: Session = Depends(db)):
    d = s.get(PdfDocument, doc_id)
    if not d:
        raise HTTPException(404)
    if not settings().anthropic_api_key:
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
        for r in s.scalars(select(RootDomain).where(RootDomain.nick_id == n.id).order_by(RootDomain.name)):
            rs.append({"name": r.name, "dns_host": r.dns_host, "expires": r.expires.isoformat() if r.expires else None,
                       "days_left": (r.expires - date.today()).days if r.expires else None, "apex_on_hosting": r.apex_on_hosting,
                       "suspended": r.suspended, "selected": r.selected, "issue": domains.root_issue(r, n), "busy": domains.root_busy(s, r.name)})
        out.append({"id": n.id, "name": n.name, "ip": n.ip, "hosting": n.hosting, "cpanel_host": n.cpanel_host, "enabled": n.enabled, "roots": rs})
    return out


class SelectBody(BaseModel):
    names: list[str]
    on: bool


@app.post("/api/domains/roots/select")
def select_roots(body: SelectBody, s: Session = Depends(db)):
    return domains.set_selected(s, body.names, body.on)


@app.get("/api/domains/rows")
def domain_rows(s: Session = Depends(db)):
    return domains.scan(s)


class RunBody(BaseModel):
    items: list[dict]


@app.post("/api/domains/run")
def domain_run(body: RunBody, s: Session = Depends(db)):
    if not any(r.selected for r in s.scalars(select(RootDomain))):
        raise HTTPException(422, "Chưa tích chọn miền gốc nào — không bắt đầu")
    return domains.enqueue_rows(s, body.items)


# ───────── Websites ─────────

@app.get("/api/websites/templates")
def templates():
    return [{"id": t.id, "name": t.name, "group": t.group, "primary": t.primary, "accent": t.accent, "hero": t.hero,
             "photo_keywords": list(t.photo_keywords), "industries": list(t.industries)} for t in TEMPLATES]


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
