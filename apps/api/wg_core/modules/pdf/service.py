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
from ...runtime_config import get as cfg
from ...integrations import ai
from ...integrations.errors import Conflict, Permanent
from ...integrations.google import Drive, Sheets, hyperlink_formula
from ...jobs import JobContext, enqueue, handler
from ...models import PdfDocument, SheetWrite
from ..websites.templates import detect as detect_template, template_for_cnae
from .extract import detect, extract_text_layer, fields_from_ai, locate, read_pdf
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
    if doc.status == "needs_ai":
        request_scan_read(s, doc)  # scans: free OCR on this machine first (AI only if OCR does not know the form)
    return doc, True


def extract_into(doc: PdfDocument, data: bytes, forced_type: str | None = None):
    t = read_pdf(data)
    doc.pages, doc.has_text = t.pages, len(t.text.strip()) > 20
    det = detect(t)
    doc.doc_type = forced_type or det.doc_type
    doc.detection_confidence = 1.0 if forced_type else det.confidence
    doc.detection_reason = "Chọn thủ công" if forced_type else det.reason
    doc.error = None
    read = extract_text_layer(t, doc.doc_type) if doc.has_text else None
    if read:
        doc.fields, doc.extra = read
        locate(data, doc.fields)  # page + region of every value, shown next to the cell
        doc.status = "review"
    elif not doc.has_text and doc.doc_type in ("ca", "wy", "wa", "br", "unknown"):
        # Scan without a text layer: the AI job identifies the form (unless picked by hand) and reads it.
        doc.fields, doc.status = {}, "needs_ai"
    else:
        doc.fields, doc.status = {k: field("", "missing") for k in FIELD_KEYS}, "review"
    doc.industry = industry_for(doc) if doc.fields else {}


def request_scan_read(s: Session, doc: PdfDocument):
    return enqueue(s, "pdf_ocr_read", f"pdf_ocr:{doc.md5}", {"doc_id": doc.id}, resource="ocr")


@handler("pdf_ocr_read")
def _ocr_read(ctx: JobContext):
    """Scanned page → RapidOCR on this machine (free, nothing sent out) → the boxes of a known form. A form the reader
    does not know goes to the AI when a key is set; otherwise the owner picks the type or types the cells."""
    from .ocr import extract_ca_scan, ocr_document

    doc = ctx.session.get(PdfDocument, ctx.job.payload["doc_id"])
    ctx.step("OCR bản scan (miễn phí, trên máy)")
    data = storage_path(doc.md5).read_bytes()
    pages = ocr_document(data)  # every page, turned upright
    got = extract_ca_scan(pages, data)
    manual = doc.detection_reason == "Chọn thủ công"
    if got and (not manual or doc.doc_type == "ca"):
        doc.fields, doc.extra = got
        doc.doc_type, doc.status, doc.error = "ca", "review", None
        if not manual:
            doc.detection_confidence = 0.9
            doc.detection_reason = (f"OCR: mẫu {doc.extra['version']} · State of California · Secretary of State"
                                    + ("" if doc.extra.get("version_verified") else " · phiên bản chưa kiểm chứng"))
        doc.industry = industry_for(doc)
        ctx.log(f"OCR đọc xong {doc.extra['version']} ({doc.extra['pages_read']} trang) — mọi ô đọc bằng OCR cần anh đánh dấu "
                f"đã kiểm tra trước khi lưu", "ok")
        return
    if cfg("ANTHROPIC_API_KEY"):
        request_ai_read(ctx.session, doc)
        ctx.log("OCR chưa biết mẫu phôi này — chuyển cho AI đọc", "info")
        return
    doc.error = "OCR chưa biết mẫu phôi này (đang đọc được: California LLC-1, LLC-5) — nhập tay các ô, hoặc báo em mẫu mới"
    ctx.log(doc.error, "warn")


def request_ai_read(s: Session, doc: PdfDocument):
    return enqueue(s, "pdf_ai_read", f"pdf_ai:{doc.md5}", {"doc_id": doc.id}, resource="ai")


@handler("pdf_ai_read")
def _ai_read(ctx: JobContext):
    doc = ctx.session.get(PdfDocument, ctx.job.payload["doc_id"])
    ctx.step("AI đọc bản scan")
    result = ai.read_scanned_pdf(storage_path(doc.md5).read_bytes())
    ai_type = result.get("doc_type", "unknown")
    if doc.detection_reason != "Chọn thủ công":
        doc.doc_type = ai_type
        doc.detection_confidence = 0.0 if ai_type == "unknown" else 0.9
        doc.detection_reason = f"AI nhận diện từ bản scan: {result.get('evidence', '')}".strip()
    elif ai_type not in (doc.doc_type, "unknown"):
        ctx.log(f"AI cho rằng đây là loại {ai_type}, khác loại đã chọn tay ({doc.doc_type}) — giữ loại đã chọn, cần kiểm tra", "warn")
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
    # Owner's rule (2026-10-19): nothing read from an image goes to Drive / the Sheet before the owner checked it
    # against the page — a cell read by OCR or AI must be ticked "đã kiểm tra" (or typed by hand).
    unchecked = [k for k, f in doc.fields.items() if isinstance(f, dict) and f.get("value") and f.get("source") in ("ocr", "ai")
                 and not f.get("checked")]
    if unchecked:
        reasons.append(f"Ô {', '.join(sorted(unchecked))} đọc từ ảnh scan — anh đánh dấu “đã kiểm tra” từng ô trước khi lưu")
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

    if not ctx.state.get("dup_checked") and not doc.sheet_row:  # already written by an earlier run → nothing to check
        ctx.step("Kiểm tra trùng")
        for other in s.scalars(select(PdfDocument).where(PdfDocument.id != doc.id, PdfDocument.status == "saved")):
            if (other.fields.get("J") or {}).get("value") == j and (other.fields.get("H") or {}).get("value") == h:
                doc.status, doc.error = "failed", f"Trùng mã {j} ({h}) với file đã lưu “{other.original_name}”"
                raise Conflict(doc.error)
        for r in Sheets().read_rows():
            if r.cells["J"].strip() == j and r.cells["H"].strip() == h and r.row != doc.sheet_row:
                doc.status, doc.error = "failed", f"Sheet đã có mã {j} ({h}) ở dòng {r.row} — không thêm trùng"
                raise Conflict(doc.error)
        ctx.checkpoint(dup_checked=True)
        ctx.log("Không trùng (database + Sheet)", "ok")

    if not doc.drive_file_id:
        ctx.step("Upload PDF gốc lên Drive")
        drive = Drive()
        res = drive.find_by_md5(doc.md5)  # uploaded before (e.g. crash before the ID was saved) → reuse, never twice
        if res:
            ctx.log("Drive đã có file cùng nội dung (md5) do app upload trước đó → dùng lại, không upload lần 2", "info")
        else:
            res = drive.upload_pdf(doc.original_name, storage_path(doc.md5).read_bytes(), doc.md5)
        if res.get("md5Checksum") != doc.md5:
            raise Permanent(f"md5 trên Drive ({res.get('md5Checksum')}) khác file gốc ({doc.md5}) — dừng, không ghi Sheet")
        doc.drive_file_id, doc.drive_link = res["id"], res.get("webViewLink") or f"https://drive.google.com/file/d/{res['id']}/view"
        ctx.checkpoint(drive_file_id=doc.drive_file_id)
        ctx.log(f"Drive: đã upload, md5 khớp, ID {doc.drive_file_id}", "ok")
    else:
        ctx.log("Đã có Drive ID từ lượt trước → không upload lại", "info")

    if not doc.sheet_row and ctx.state.get("append_tried"):
        # An earlier attempt sent the row but did not get (or save) the answer: Sheets may have written it.
        ctx.step("Kiểm tra dòng đã ghi ở lượt trước")
        for r in Sheets().read_rows():
            if r.cells["J"].strip() == j and r.cells["H"].strip() == h and doc.drive_file_id in r.cells["K"]:
                doc.sheet_row = r.row
                ctx.checkpoint(sheet_row=r.row)
                ctx.log(f"Dòng {r.row} đã được ghi ở lượt trước (cùng J, H, Drive ID) → dùng lại, không thêm dòng trùng", "warn")
                break

    if not doc.sheet_row:
        ctx.step("Ghi Google Sheet (A, D–K)")
        sheets = Sheets()
        values = row_values(doc)
        ctx.checkpoint(append_tried=True)
        row = sheets.append_row(values)
        doc.sheet_row = row
        s.add(SheetWrite(tab=sheets.tab, range=f"A{row}:K{row}", old_value=None, new_value=" | ".join(values), job_id=ctx.job.id))
        ctx.checkpoint(sheet_row=row)
        ctx.log(f"Đã ghi dòng {row}: A, D–J · B, C trống", "ok")

    if not ctx.state.get("k_link"):
        ctx.step("Ghi K = “Xem phôi”")
        sheets = Sheets()
        formula = hyperlink_formula(doc.drive_link)
        sheets.write_cell(f"K{doc.sheet_row}", formula, user_entered=True)
        s.add(SheetWrite(tab=sheets.tab, range=f"K{doc.sheet_row}", old_value=doc.drive_link, new_value=formula, job_id=ctx.job.id))
        ctx.checkpoint(k_link=True)
        ctx.log(f"K{doc.sheet_row} = “Xem phôi” → PDF gốc trên Drive", "ok")
    doc.status, doc.error = "saved", None
