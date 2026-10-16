"""PDF Manager: ingest → detect/extract → review (UI) → save job (Drive → md5 check → Drive ID → Sheet).

Save order (never reversed): duplicate check (DB md5, DB J+H, live Sheet J+H) → upload original bytes to Drive →
verify md5 → store Drive ID → append ONE row A, D–K (B and C empty, L untouched, K = Drive link).
If the Sheet write fails the Drive ID is kept and the retry only writes the Sheet.
"""
import hashlib
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...config import settings
from ...integrations import ai
from ...integrations.errors import Conflict, Permanent
from ...integrations.google import Drive, Sheets
from ...jobs import JobContext, enqueue, handler
from ...models import PdfDocument, SheetWrite
from ..websites.templates import detect as detect_template, template_for_cnae
from .extract import detect, extract_br, extract_wy, fields_from_ai, read_pdf
from .fields import FIELD_KEYS, blocking, field, short_name, validate


def storage_path(md5: str) -> Path:
    p = settings().data_dir / "pdf"
    p.mkdir(parents=True, exist_ok=True)
    return p / f"{md5}.pdf"


def industry_for(doc: PdfDocument) -> dict:
    if doc.doc_type == "br" and doc.extra.get("cnae_principal"):
        t = template_for_cnae(doc.extra["cnae_principal"])
        if t:
            return {"raw": doc.extra["cnae_principal"], "template": t.id, "source": "doc"}
    name = (doc.fields.get("A") or {}).get("value", "")
    t, kw = detect_template(name)
    return {"raw": kw or "", "template": t.id, "source": "name", "note": "Gợi ý từ tên công ty — chưa xác minh"}


def ingest(s: Session, name: str, data: bytes) -> tuple[PdfDocument, bool]:
    """Store + read one PDF. Returns (doc, is_new). Same bytes twice → the existing record (no duplicate)."""
    if not data.startswith(b"%PDF"):
        raise Permanent("File không phải PDF")
    md5 = hashlib.md5(data).hexdigest()
    existing = s.scalar(select(PdfDocument).where(PdfDocument.md5 == md5))
    if existing:
        return existing, False
    storage_path(md5).write_bytes(data)
    doc = PdfDocument(md5=md5, original_name=name, size=len(data), fields={}, extra={}, industry={})
    s.add(doc)
    s.flush()
    extract_into(doc, data)
    return doc, True


def extract_into(doc: PdfDocument, data: bytes, forced_type: str | None = None):
    t = read_pdf(data)
    doc.pages, doc.has_text = t.pages, len(t.text.strip()) > 20
    det = detect(t)
    doc.doc_type = forced_type or det.doc_type
    doc.detection_confidence = 1.0 if forced_type else det.confidence
    doc.detection_reason = "Chọn thủ công" if forced_type else det.reason
    doc.error = None
    if doc.doc_type == "br" and doc.has_text:
        doc.fields, doc.extra = extract_br(t)
        doc.status = "review"
    elif doc.doc_type == "wy" and doc.has_text:
        doc.fields, doc.extra = extract_wy(t)
        doc.status = "review"
    elif doc.doc_type == "ca":
        doc.fields, doc.status = {}, "needs_ai"  # read by the pdf_ai_read job
    else:
        doc.fields, doc.status = {k: field("", "missing") for k in FIELD_KEYS}, "review"
    doc.industry = industry_for(doc) if doc.fields else {}


def request_ai_read(s: Session, doc: PdfDocument):
    return enqueue(s, "pdf_ai_read", f"pdf_ai:{doc.md5}", {"doc_id": doc.id}, resource="ai")


@handler("pdf_ai_read")
def _ai_read(ctx: JobContext):
    doc = ctx.session.get(PdfDocument, ctx.job.payload["doc_id"])
    ctx.step("AI đọc bản scan")
    result = ai.read_scanned_pdf(storage_path(doc.md5).read_bytes(), doc.doc_type)
    doc.fields = fields_from_ai(result, doc.doc_type)
    doc.industry = industry_for(doc)
    doc.status = "review"
    ctx.log("AI đã đọc phôi — mọi ô do AI đọc phải được đối chiếu trước khi lưu", "ok")


# ───────── save ─────────

def save_check(doc: PdfDocument, confirm_missing: bool, critical_checked: bool) -> list[str]:
    """Reasons the document cannot be saved yet (empty list = OK)."""
    reasons = []
    if doc.doc_type == "unknown":
        reasons.append("Chưa nhận diện loại phôi")
    errs = blocking(validate(doc.fields, doc.doc_type))
    for k, v in errs.items():
        if v["kind"] == "missing" and confirm_missing:
            continue
        reasons.append(f"{k}: {v['message']}")
    if any((doc.fields.get(k) or {}).get("source") == "ai" for k in ("A", "J")) and not critical_checked:
        reasons.append("A/J do AI đọc từ bản scan — cần tick “đã đối chiếu”")
    return reasons


def request_save(s: Session, doc: PdfDocument):
    doc.status = "queued"
    return enqueue(s, "pdf_save", f"pdf:{doc.md5}", {"doc_id": doc.id})


def row_values(doc: PdfDocument) -> list[str]:
    v = lambda k: (doc.fields.get(k) or {}).get("value", "")  # noqa: E731
    e = v("E") or short_name(v("A"))
    # A, B(empty), C(empty), D, E, F, G, H, I, J, K — L is never written
    return [v("A"), "", "", v("D"), e, v("F"), v("G"), v("H"), v("I"), v("J"), doc.drive_link or ""]


@handler("pdf_save")
def _save(ctx: JobContext):
    s, doc = ctx.session, ctx.session.get(PdfDocument, ctx.job.payload["doc_id"])
    j = (doc.fields.get("J") or {}).get("value", "")
    h = (doc.fields.get("H") or {}).get("value", "")

    if not ctx.state.get("dup_checked"):
        ctx.step("Kiểm tra trùng")
        for other in s.scalars(select(PdfDocument).where(PdfDocument.id != doc.id, PdfDocument.status == "saved")):
            if (other.fields.get("J") or {}).get("value") == j and (other.fields.get("H") or {}).get("value") == h:
                doc.status, doc.error = "failed", f"Trùng mã {j} ({h}) với file đã lưu “{other.original_name}”"
                raise Conflict(doc.error)
        for r in Sheets().read_rows():
            if r.cells["J"].strip() == j and r.cells["H"].strip() == h:
                doc.status, doc.error = "failed", f"Sheet đã có mã {j} ({h}) ở dòng {r.row} — không thêm trùng"
                raise Conflict(doc.error)
        ctx.checkpoint(dup_checked=True)
        ctx.log("Không trùng (database + Sheet)", "ok")

    if not doc.drive_file_id:
        ctx.step("Upload PDF gốc lên Drive")
        data = storage_path(doc.md5).read_bytes()
        res = Drive().upload_pdf(doc.original_name, data)
        if res.get("md5Checksum") != doc.md5:
            raise Permanent(f"md5 trên Drive ({res.get('md5Checksum')}) khác file gốc ({doc.md5}) — dừng, không ghi Sheet")
        doc.drive_file_id, doc.drive_link = res["id"], res.get("webViewLink") or f"https://drive.google.com/file/d/{res['id']}/view"
        ctx.checkpoint(drive_file_id=doc.drive_file_id)
        ctx.log(f"Drive: đã upload, md5 khớp, ID {doc.drive_file_id}", "ok")
    else:
        ctx.log("Đã có Drive ID từ lượt trước → không upload lại", "info")

    if not doc.sheet_row:
        ctx.step("Ghi Google Sheet (A, D–K)")
        sheets = Sheets()
        values = row_values(doc)
        row = sheets.append_row(values)
        doc.sheet_row = row
        s.add(SheetWrite(tab=sheets.s.sheet_tab, range=f"A{row}:K{row}", old_value=None, new_value=" | ".join(values), job_id=ctx.job.id))
        ctx.checkpoint(sheet_row=row)
        ctx.log(f"Đã ghi dòng {row}: A, D–K · B, C trống · K = link PDF gốc", "ok")
    doc.status, doc.error = "saved", None
