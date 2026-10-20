"""Read a folder of PDFs straight into one results file — no database, nothing written to Google (owner, 2026-10-20).

    python -m wg_core.modules.pdf.batch "C:/…/Ảnh Phôi" [more PDFs or folders…] [--out file.xlsx] [--open]
    (or the Desktop shortcut "Đọc phôi PDF": pick the PDFs, the result opens in Excel when done)

One PDF at a time: read → extract → its row added → the .xlsx saved → the PDF freed. A file needing review still gets
its candidates in the row (the owner fixes one letter in Excel instead of reading the scan again); status and reason
say what to check. Sheets: KET_QUA (A–J layout, F = full address) and CAN_DUYET (review rows only) — xlsx_out.py."""
import argparse
import gc
import hashlib
import sys
import time
from pathlib import Path

COLUMNS = ["source_file", "check", "entity_name", "business_full_address", "business_street", "business_city", "business_state",
           "business_zip", "state_file_number", "document_type", "status", "confidence", "reason", "address_source"]


def _street(full: str, city: str, state: str, code: str) -> str:
    """F is the full address; the street column is F without its trailing ", CITY, ST ZIP"."""
    from .extract import us_style_address

    tail = us_style_address("", city, state, code)
    return full[: -len(tail)].rstrip(", ") if tail and full.endswith(tail) else full


def _text_layer_row(data: bytes) -> dict | None:
    """WA / Brazil / Wyoming PDFs with a usable text layer: the same readers as the app."""
    from .extract import detect, extract_text_layer, read_pdf
    from .service import text_layer_problem

    t = read_pdf(data)
    if len(t.text.strip()) <= 20:
        return None
    det = detect(t)
    read = extract_text_layer(t, det.doc_type)
    if not read or text_layer_problem(t, det.doc_type, read):
        return None
    f, extra = read
    v = lambda k: (f.get(k) or {}).get("value", "")  # noqa: E731
    return {"entity_name": v("A"), "business_full_address": v("F"), "business_street": _street(v("F"), v("G"), v("H"), v("I")),
            "business_city": v("G"), "business_state": v("H"), "business_zip": v("I"), "state_file_number": v("J"),
            "document_type": det.doc_type, "status": extra.get("status", "OK"), "confidence": 100,
            "reason": f"Lớp chữ PDF ({det.reason})"}


def _scan_row(data: bytes, force: bool = False) -> dict:
    from .ocr import read_scan

    r = read_scan(data, force=force)
    sheet = r.pop("sheet")
    fields = sheet[0] if sheet else {}
    v = lambda k: (fields.get(k) or {}).get("value", "")  # noqa: E731
    confs = [f["confidence"] for f in (fields.get(k) or {} for k in "AJF") if f.get("value") and isinstance(f.get("confidence"), int)]
    doubts = [f"{k}: {(fields.get(k) or {}).get('suspects')[0]['message']}" for k in "AJFGHI" if (fields.get(k) or {}).get("suspects")]
    return {"entity_name": v("A") or ((fields.get("A") or {}).get("unreadable") or [""])[0],
            "business_full_address": v("F"), "business_street": (fields.get("F") or {}).get("street", ""),
            "business_city": v("G"), "business_state": v("H"), "business_zip": v("I"), "state_file_number": v("J"),
            "document_type": r.get("document_type") or "", "status": r.get("status") or "",
            "confidence": min(confs) if confs else "",
            "reason": "; ".join([r.get("reason") or ""] + [d for d in doubts if d.split(": ", 1)[1] not in (r.get("reason") or "")]),
            # the box F–I came from, and its role (only a principal / principal executive office / mailing box is used)
            "address_source": "; ".join(f"{c['role']}: {c['reason']}" for c in r.get("selected_candidates") or [])}


# what the owner does with each row (the "check" column, to filter in Excel)
CHECK = {"OK": "OK", "NO_BUSINESS_ADDRESS_ON_FORM": "OK — phôi không có ô địa chỉ (F–I trống)",
         "REVIEW_REQUIRED": "CẦN DUYỆT — sửa theo cột reason", "LOW_CONFIDENCE": "CẦN DUYỆT — độ tin cậy thấp",
         "UNKNOWN_DOCUMENT": "KHÔNG ĐỌC — mẫu chưa biết", "OCR_FAILED": "KHÔNG ĐỌC — OCR không ra chữ",
         "ERROR": "KHÔNG ĐỌC — lỗi khi đọc file"}


def pdf_files(paths: list[Path]) -> list[Path]:
    """The PDFs picked: files as given, folders → their *.pdf (not subfolders), in name order."""
    out = []
    for p in paths:
        out += sorted(p.glob("*.pdf"), key=lambda f: f.name.lower()) if p.is_dir() else [p] if p.suffix.lower() == ".pdf" else []
    return out


def run(paths: list[Path] | Path, out: Path, force: bool = False) -> dict:
    from . import xlsx_out

    out.parent.mkdir(parents=True, exist_ok=True)
    files = pdf_files(paths if isinstance(paths, list) else [paths])
    seen, stats = set(), {"files": 0, "duplicates": 0, "seconds": 0.0, "status": {}, "total": len(files)}
    rows: list[dict] = []  # small text rows only (the PDFs and pages are freed after each file)
    for pdf in files:
        data = pdf.read_bytes()
        sha = hashlib.sha256(data).hexdigest()
        if sha in seen:  # the same file under another name ("… - Copy.pdf")
            stats["duplicates"] += 1
            continue
        seen.add(sha)
        t0 = time.time()
        try:
            row = _text_layer_row(data) or _scan_row(data, force)
        except Exception as e:  # noqa: BLE001 — one bad file never stops the batch
            row = {"status": "ERROR", "reason": f"{type(e).__name__}: {e}"}
        if row.get("status") in ("UNKNOWN_DOCUMENT", "OCR_FAILED", "ERROR"):  # nothing guessed for these
            row = {"status": row["status"], "reason": row.get("reason", ""), "document_type": row.get("document_type", "")}
        rows.append({**{c: "" for c in COLUMNS}, **row, "source_file": pdf.name, "check": CHECK.get(row.get("status"), "CẦN DUYỆT")})
        xlsx_out.write(rows, out)  # the row is on disk before the next PDF is opened
        stats["files"] += 1
        stats["seconds"] += time.time() - t0
        stats["status"][row.get("status")] = stats["status"].get(row.get("status"), 0) + 1
        print(f"{stats['files'] + stats['duplicates']:>3}/{len(files)} {pdf.name:<30} {row.get('status', ''):<28} "
              f"{row.get('entity_name', '')[:50]}", flush=True)
        del data, row
        gc.collect()
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", type=Path, nargs="+", help="file PDF và/hoặc thư mục chứa PDF")
    ap.add_argument("--out", type=Path, default=None, help="mặc định: data/reports/ket-qua-<ngày-giờ>.xlsx")
    ap.add_argument("--force", action="store_true", help="đọc lại OCR, bỏ qua cache")
    ap.add_argument("--open", action="store_true", help="mở file kết quả khi xong")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    from ... import runtime_config

    runtime_config.OFFLINE = True  # no database, no Google: PDFs in, one results file out
    out = a.out or Path("data/reports") / f"ket-qua-{time.strftime('%Y%m%d-%H%M%S')}.xlsx"
    s = run(a.paths, out, a.force)
    print(f"Xong {s['files']} file ({s['duplicates']} file trùng nội dung bỏ qua) — {round(s['seconds'])} giây")
    for st, n in sorted(s["status"].items(), key=lambda kv: -kv[1]):
        print(f"  {st}: {n}")
    print(f"Kết quả: {out.resolve()}")
    if a.open and s["files"]:
        import os

        os.startfile(out.resolve())  # noqa: S606 — Windows: opens the .xlsx in Excel


if __name__ == "__main__":
    main()
