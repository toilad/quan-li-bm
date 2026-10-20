"""PDF inbox folder (owner, 2026-10-20): drop PDFs into one folder (Desktop\\Ảnh Phôi) and the worker reads each new
one exactly like an upload (read → auto-save to the Sheet). Once a file is done — its row is on the Sheet with the
Drive copy's md5 checked, or the Sheet / app already had it (duplicate) — the file is deleted from the folder for good:
the original stays on Drive (column K). A file still to review, unknown or not read stays in the folder."""
import hashlib
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...runtime_config import get as cfg
from ...models import PdfDocument
from .service import ingest

_sizes: dict[str, int] = {}  # size seen at the last pass: a file still being copied is left for the next one
_md5s: dict[tuple, str] = {}  # (path, size, mtime) → md5, so the status line does not re-read every file


def inbox_dir() -> Path | None:
    v = (cfg("PDF_INBOX_DIR", "") or "").strip()
    if v.lower() in ("off", "false", "0"):
        return None
    return Path(v) if v else Path.home() / "Desktop" / "Ảnh Phôi"


def pdf_files(d: Path) -> list[Path]:
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")


def done_reason(doc: PdfDocument | None) -> str:
    """Why the folder copy is no longer needed ("" = keep it)."""
    if not doc:
        return ""
    if doc.status == "saved" and doc.drive_file_id and doc.sheet_row:
        return f"đã ghi Sheet dòng {doc.sheet_row}, bản gốc trên Drive"
    if doc.status == "failed" and (doc.extra or {}).get("duplicate"):
        return "trùng — Sheet / app đã có"
    return ""


def scan(s: Session, log=print) -> dict:
    """One pass over the folder: read the new PDFs, delete the finished ones. Never raises for a single file."""
    d = inbox_dir()
    out = {"dir": str(d) if d else "", "read": 0, "deleted": 0, "kept": 0}
    if not d or not d.is_dir():
        return out
    for f in pdf_files(d):
        try:
            size = f.stat().st_size
            if _sizes.get(str(f)) != size:  # new or still growing → look again next pass
                _sizes[str(f)] = size
                out["kept"] += 1
                continue
            data = f.read_bytes()
            if not data.startswith(b"%PDF") or b"%%EOF" not in data[-2048:]:
                out["kept"] += 1  # not a PDF, or not fully copied yet
                continue
            md5 = hashlib.md5(data).hexdigest()
            doc = s.scalar(select(PdfDocument).where(PdfDocument.md5 == md5))
            if not doc:
                doc, _ = ingest(s, f.name, data)
                s.commit()
                out["read"] += 1
                log(f"Thư mục phôi: đọc {f.name}")
            why = done_reason(doc)
            if why and hashlib.md5(f.read_bytes()).hexdigest() == md5:  # still the same file → delete for good
                os.remove(f)
                _sizes.pop(str(f), None)
                out["deleted"] += 1
                log(f"Thư mục phôi: đã xoá {f.name} ({why})")
            else:
                out["kept"] += 1
        except Exception as e:  # noqa: BLE001 — a locked / bad file never stops the folder
            s.rollback()
            out["kept"] += 1
            log(f"Thư mục phôi: bỏ qua {f.name} lần này — {type(e).__name__}: {e}")
    return out


def status(s: Session) -> dict:
    """What is still in the folder, for the PDF page: waiting to be read / saved, to review, not readable."""
    d = inbox_dir()
    res = {"dir": str(d) if d else "", "on": bool(d and d.is_dir()), "files": 0, "pending": 0, "review": 0, "other": 0}
    if not res["on"]:
        return res
    for f in pdf_files(d):
        res["files"] += 1
        try:
            st = f.stat()
            k = (str(f), st.st_size, st.st_mtime_ns)
            md5 = _md5s.get(k) or _md5s.setdefault(k, hashlib.md5(f.read_bytes()).hexdigest())
        except OSError:
            res["pending"] += 1
            continue
        doc = s.scalar(select(PdfDocument).where(PdfDocument.md5 == md5))
        if not doc or doc.status in ("uploaded", "needs_ai", "queued") or done_reason(doc):
            res["pending"] += 1
        elif doc.status == "review" and (doc.extra or {}).get("status") not in ("UNKNOWN_DOCUMENT", "OCR_FAILED"):
            res["review"] += 1
        else:
            res["other"] += 1
    return res
