"""Column A = the company's legal name as verified on the PDF (owner's rules, 2026-10-19).

- New company: A is the name read from the legal-name box of the form, checked by the owner against the page.
- Company already in the Sheet (same registration number + state — the existing duplicate rule): when the PDF name
  differs from column A, both are shown; only after the owner confirms is A of THAT row rewritten. No other row, no
  other column, no new row.
- Nothing happens while the name is not verified (an OCR / AI reading the owner has not ticked "đã kiểm tra").
- The first reading is kept on the cell (read_value) and every rename is logged (SheetWrite + doc.extra["renames"]).
"""
import re
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from ...integrations.errors import Conflict, Permanent
from ...models import PdfDocument, SheetWrite


def norm_id(j: str) -> str:
    """Registration numbers compared by their digits ("603 622 707" = "603622707"; "00.001.441/0001-08" = "0000144100108");
    leading zeros a number-formatted cell may have dropped are ignored."""
    return re.sub(r"\D", "", j or "").lstrip("0")


def same_company(cells: dict, j: str, h: str) -> bool:
    n = norm_id(j)
    return bool(n) and norm_id(cells.get("J", "")) == n and (cells.get("H", "") or "").strip().upper() == (h or "").strip().upper()


def same_name(a: str, b: str) -> bool:
    """Exact legal name: spelling, punctuation, suffix and case count; only extra spaces do not."""
    return " ".join((a or "").split()) == " ".join((b or "").split())


def name_verified(doc: PdfDocument) -> tuple[bool, str]:
    a = doc.fields.get("A") or {}
    if not a.get("value"):
        return False, "Chưa có tên công ty (A)"
    if a.get("source") == "manual" or a.get("checked"):
        return True, ""
    return False, "Tên (A) chưa được đối chiếu với ảnh gốc — anh xem vùng ảnh bên cạnh ô A rồi tick “Đã kiểm tra”"


def _key(doc: PdfDocument) -> tuple[str, str, str]:
    v = lambda k: ((doc.fields.get(k) or {}).get("value") or "").strip()  # noqa: E731
    return v("A"), v("J"), v("H")


def match(doc: PdfDocument, rows=None) -> dict:
    """Read-only: where this company is in the Sheet and whether its name differs."""
    from ...integrations.google import Sheets

    name, j, h = _key(doc)
    verified, why = name_verified(doc)
    out = {"pdf_name": name, "j": j, "h": h, "name_verified": verified, "why": why, "rows": [], "status": "new",
           "evidence": (doc.fields.get("A") or {}).get("region")}
    if not norm_id(j) or not h:
        out["status"] = "no_key"
        out["why"] = "Thiếu mã định danh (J) hoặc bang (H) — chưa đối chiếu được với Sheet"
        return out
    rows = rows if rows is not None else Sheets().read_rows()
    hits = [r for r in rows if same_company(r.cells, j, h)]
    out["rows"] = [{"row": r.row, "A": r.cells.get("A", ""), "B": r.cells.get("B", ""), "C": r.cells.get("C", "")} for r in hits]
    if len(hits) > 1:
        out["status"] = "ambiguous"  # several rows with the same number + state: the owner sorts it out by hand
    elif hits:
        out["status"] = "same_name" if same_name(hits[0].cells.get("A", ""), name) else "name_differs"
    return out


def rename(s: Session, doc: PdfDocument, row: int, expected_old: str) -> dict:
    """Owner confirmed: column A of `row` becomes the verified PDF name. Re-checked on the live Sheet first."""
    from ...integrations.google import Sheets

    name, j, h = _key(doc)
    verified, why = name_verified(doc)
    if not verified:
        raise Permanent(why)
    sheets = Sheets()
    live = next((r for r in sheets.read_rows() if r.row == row), None)
    if not live or not same_company(live.cells, j, h):
        raise Permanent(f"Dòng {row} không có cùng mã {j} và bang {h} — không đổi tên dòng này")
    if sum(1 for r in sheets.read_rows() if same_company(r.cells, j, h)) > 1:
        raise Permanent(f"Sheet có nhiều dòng cùng mã {j} ({h}) — anh xử lý tay, app không chọn hộ")
    old = live.cells.get("A", "")
    if not same_name(old, expected_old):
        raise Conflict(f"Ô A{row} vừa đổi thành “{old}” (khác “{expected_old}” lúc anh xem) — xem lại rồi xác nhận lần nữa")
    if same_name(old, name):
        return {"row": row, "changed": False, "old": old, "new": name}
    sheets.write_cell(f"A{row}", name)  # RAW: the name exactly as verified
    s.add(SheetWrite(tab=sheets.tab, range=f"A{row}", old_value=old, new_value=name, job_id=None))
    a = doc.fields.get("A") or {}
    entry = {"row": row, "old": old, "new": name, "read_value": a.get("read_value") or a.get("value"),
             "source": a.get("source"), "at": datetime.now(timezone.utc).isoformat()}
    doc.extra = {**(doc.extra or {}), "renames": [*(doc.extra or {}).get("renames", []), entry]}
    return {**entry, "changed": True}


def drive_name(doc: PdfDocument) -> str:
    """The original PDF goes to Drive under the company's verified legal name (the owner's existing files are named that
    way); characters Drive / Windows do not like are replaced. Falls back to the uploaded file name."""
    name = ((doc.fields.get("A") or {}).get("value") or "").strip()
    clean = " ".join(re.sub(r'[\\/:*?"<>|\x00-\x1f]', " ", name).split())[:150].rstrip(" .")
    return f"{clean}.pdf" if clean else doc.original_name
