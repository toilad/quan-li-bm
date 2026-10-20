"""Read a folder of PDFs straight into one results file — no database, nothing written to Google (owner, 2026-10-20).

    python -m wg_core.modules.pdf.batch "C:/…/Ảnh Phôi" [--out data/reports/extracted_results.csv]

One PDF at a time: read → extract → append its row → free it. A file needing review still gets its candidates in the
row (the owner fixes one letter in Excel instead of reading the scan again); status and reason say what to check.
CSV in UTF-8 with BOM, so Excel opens it with the accents intact."""
import argparse
import csv
import gc
import hashlib
import sys
import time
from pathlib import Path

COLUMNS = ["source_file", "entity_name", "business_full_address", "business_street", "business_city", "business_state",
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


def run(folder: Path, out: Path, force: bool = False) -> dict:
    out.parent.mkdir(parents=True, exist_ok=True)
    new = not out.exists() or out.stat().st_size == 0
    seen, stats = set(), {"files": 0, "duplicates": 0, "seconds": 0.0}
    with out.open("a", newline="", encoding="utf-8-sig" if new else "utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=COLUMNS)
        if new:
            w.writeheader()
        for pdf in sorted(folder.glob("*.pdf")):
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
            w.writerow({**{c: "" for c in COLUMNS}, **row, "source_file": pdf.name})
            fh.flush()  # the row is on disk before the next PDF is opened
            stats["files"] += 1
            stats["seconds"] += time.time() - t0
            print(f"{stats['files']:>3} {pdf.name:<30} {row.get('status', ''):<28} {row.get('entity_name', '')[:50]}", flush=True)
            del data, row
            gc.collect()
    return stats


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("folder", type=Path)
    ap.add_argument("--out", type=Path, default=Path("data/reports/extracted_results.csv"))
    ap.add_argument("--force", action="store_true", help="đọc lại OCR, bỏ qua cache")
    a = ap.parse_args(argv)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    s = run(a.folder, a.out, a.force)
    print(f"Xong {s['files']} file ({s['duplicates']} file trùng nội dung bỏ qua) — {round(s['seconds'])} giây → {a.out}")


if __name__ == "__main__":
    main()
