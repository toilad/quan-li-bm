"""What makes a reading usable, per document type (owner, 2026-10-19): no fixed "A and J required" list — each type
says which cells it must have, which cells must match a format when present, and whether the form has a box for the
company's own address at all. Text layer and OCR are never merged silently: when both read a cell, they must agree."""
import re

CNPJ = r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}"
US_ADDR = {"H": r"[A-Z]{2}", "I": r"\d{5}(-\d{4})?"}

# required: cells without which the reading is not usable; format: checked only when the cell has a value;
# has_address: the form has a business-address box (False → empty F–I is the right answer, not a failure)
RULES = {
    "br": {"required": ("A", "J", "F"), "format": {"J": CNPJ, "I": r"\d{8}|\d{2}\.\d{3}-\d{3}"}, "has_address": True},
    "wa": {"required": ("A",), "format": {"J": r"\d{9}"}, "has_address": True},
    "wy": {"required": ("A",), "format": US_ADDR, "has_address": True},
    # California scans, by form (and layout: the 2005–2007 LLC-1 has no business-address box, only the agent's)
    "LLC-1 2007": {"required": ("A",), "format": {"J": r"\d{12}", **US_ADDR}, "has_address": False},
    "LLC-1 2013+": {"required": ("A",), "format": {"J": r"\d{12}", **US_ADDR}, "has_address": True},
    "LLC-5 2007": {"required": ("A",), "format": {"J": r"\d{12}", **US_ADDR}, "has_address": True},
    "LP-1 2005": {"required": ("A",), "format": {"J": r"\d{12}", **US_ADDR}, "has_address": True},
}


def rule_key(doc_type: str, form: dict | None = None) -> str:
    return f"{form['form']} {form['layout']}" if form else doc_type


def _v(fields: dict, k: str) -> str:
    return ((fields.get(k) or {}).get("value") or "").strip()


def problems(key: str, fields: dict) -> list[str]:
    """Why this reading is not usable as it is ([] = it is)."""
    rule = RULES.get(key)
    if not rule:
        return [f"Chưa có quy tắc cho loại phôi {key}"]
    out = [f"Thiếu {k}: {(fields.get(k) or {}).get('note') or 'không đọc được'}" for k in rule["required"] if not _v(fields, k)]
    out += [f"{k} sai định dạng ({_v(fields, k)})" for k, rx in rule["format"].items() if _v(fields, k) and not re.fullmatch(rx, _v(fields, k))]
    if rule["has_address"] and _v(fields, "F") and not all(_v(fields, k) for k in "GHI"):
        out.append("Địa chỉ đọc được không đủ thành phố / bang / mã bưu chính")
    for k in ("J", "A"):  # contradictions inside the document (the copy printed on a later page)
        chk = (fields.get(k) or {}).get("check") or {}
        if chk.get("match") is False:
            out.append(f"{k} mâu thuẫn với bản in lại ở trang sau ({chk.get('other')})")
    return out


def _norm(s: str) -> str:
    return re.sub(r"[^A-Z0-9]", "", (s or "").upper())


def compare_sources(ocr_fields: dict, text_fields: dict) -> list[dict]:
    """Text layer vs OCR, cell by cell. The OCR value stays in the cell; the text-layer reading is kept beside it with
    its source. Any difference (including one side empty) is a conflict for the owner — no side is picked."""
    conflicts = []
    for k in ("A", "J", "F", "G", "H", "I", "D"):
        o, t = _v(ocr_fields, k), _v(text_fields, k)
        if not t:
            continue
        f = ocr_fields.setdefault(k, {"value": "", "source": "missing"})
        f["readings"] = [{"value": o, "source": "ocr", "confidence": f.get("confidence")},
                         {"value": t, "source": "text", "confidence": 100}]
        if _norm(o) == _norm(t):
            f["sources_agree"] = True
            continue
        f["sources_agree"] = False
        conflicts.append({"field": k, "ocr": o, "text": t})
    return conflicts
