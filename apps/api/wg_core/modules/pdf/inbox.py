"""PDF inbox folder (owner, 2026-10-20): drop PDFs into one folder (Desktop\\Ảnh Phôi) and the worker reads each new
one exactly like an upload (read → auto-save to the Sheet). The owner wants the disk kept small: as soon as the app
holds its own copy of the file (data/pdf, md5 checked) the folder file is deleted for good — the app reads, reviews
and uploads to Drive (column K) from its copy, so a file still to review is not lost. Only a file the app could not
take (still being copied, not a PDF) stays in the folder."""
import hashlib
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session

from ...runtime_config import get as cfg
from ...models import PdfDocument
from .service import ingest, storage_path

_sizes: dict[str, int] = {}  # size seen at the last pass: a file still being copied is left for the next one


def inbox_dir() -> Path | None:
    v = (cfg("PDF_INBOX_DIR", "") or "").strip()
    if v.lower() in ("off", "false", "0"):
        return None
    return Path(v) if v else Path.home() / "Desktop" / "Ảnh Phôi"


def pdf_files(d: Path) -> list[Path]:
    return sorted(f for f in d.iterdir() if f.is_file() and f.suffix.lower() == ".pdf")


def done_reason(doc: PdfDocument | None) -> str:
    """Why the folder copy is no longer needed ("" = keep it): the app holds the same bytes."""
    if not doc:
        return ""
    copy = storage_path(doc.md5)
    if not (copy.exists() and hashlib.md5(copy.read_bytes()).hexdigest() == doc.md5):
        return ""
    if doc.status == "saved" and doc.sheet_row:
        return f"đã ghi Sheet dòng {doc.sheet_row}"
    if doc.status == "failed" and (doc.extra or {}).get("duplicate"):
        return "trùng — Sheet / app đã có"
    return "đã nhận vào app"


def scan(s: Session, log=print) -> dict:
    """One pass over the folder: take the new PDFs into the app, delete them. Never raises for a single file."""
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
    """For the PDF page: files still in the folder — about to be taken in, or ones the app cannot take (not a PDF)."""
    d = inbox_dir()
    res = {"dir": str(d) if d else "", "on": bool(d and d.is_dir()), "files": 0, "pending": 0, "bad": 0}
    if not res["on"]:
        return res
    for f in pdf_files(d):
        res["files"] += 1
        try:
            with open(f, "rb") as fh:
                head = fh.read(5)
        except OSError:
            head = b"%PDF"  # locked: still being copied
        res["pending" if head.startswith(b"%PDF") else "bad"] += 1
    return res
