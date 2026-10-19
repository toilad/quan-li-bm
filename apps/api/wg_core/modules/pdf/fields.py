"""Sheet field helpers: normalisation and validation shared by every document type.
All codes stay TEXT (leading zeros, dots, dashes kept)."""
import re
import unicodedata

FIELD_KEYS = ["A", "D", "E", "F", "G", "H", "I", "J"]
CRITICAL = {"A", "J"}
BR_UF = set("AC AL AP AM BA CE DF ES GO MA MT MS MG PA PB PR PE PI RJ RN RS RO RR SC SP SE TO".split())
US_STATES = {"WYOMING": "WY", "CALIFORNIA": "CA"}


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if unicodedata.category(c) != "Mn")


def short_name(a: str) -> str:
    """Legacy column E: lowercase, keep the legal suffix, drop accents and symbols."""
    return re.sub(r"[^a-z0-9]", "", strip_accents(a).lower())


def field(value: str, source: str, note: str | None = None) -> dict:
    """source: text (PDF text layer) | ai (read by AI from a scan) | auto (derived) | manual | missing"""
    value = (value or "").strip()
    f = {"value": value, "source": source if value else "missing"}
    if note:
        f["note"] = note
    return f


def cnpj_valid(cnpj: str) -> bool:
    d = re.sub(r"\D", "", cnpj)
    if len(d) != 14 or len(set(d)) == 1:
        return False
    def dv(digits: str, weights: list[int]) -> str:
        s = sum(int(x) * w for x, w in zip(digits, weights)) % 11
        return "0" if s < 2 else str(11 - s)
    w1 = [5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2]
    w2 = [6] + w1
    return d[12] == dv(d[:12], w1) and d[13] == dv(d[:13], w2)


def validate(fields: dict, doc_type: str) -> dict[str, dict]:
    """{key: {level: error|warn, kind: critical|format|missing, message}}. Errors block saving; warnings don't."""
    issues: dict[str, dict] = {}
    val = lambda k: (fields.get(k) or {}).get("value", "").strip()  # noqa: E731
    for k in FIELD_KEYS:
        f = fields.get(k) or {}
        if not val(k):
            note = f.get("note") or ""
            if k in CRITICAL:
                issues[k] = {"level": "error", "kind": "critical", "message": f"Bắt buộc — {note or 'không được để trống'}"}
            elif k != "E":
                issues[k] = {"level": "error", "kind": "missing",
                             "message": f"Trống — {note + ' · ' if note else ''}xác nhận để trống trước khi lưu"}
        elif f.get("suspects"):  # a possible OCR misreading: never corrected silently, the owner decides
            issues[k] = {"level": "warn", "kind": "review", "message": "Có thể đọc nhầm: " + f["suspects"][0]["message"]}
        elif f.get("warning"):
            issues[k] = {"level": "warn", "kind": "review", "message": f["warning"]}
    j, h, i, d = val("J"), val("H"), val("I"), val("D")
    if d:
        # format, area code ↔ the company's state (H), no "555" movie numbers (wg_core/phones.py)
        from ...phones import check as check_phone

        fd = fields.get("D") or {}
        problems = check_phone(d, h, provisioned=fd.get("phone_source") == "provisioned")
        err = next((p for p in problems if p["level"] == "error"), None)
        if err:
            issues["D"] = {"level": "error", "kind": "format", "message": err["message"]}
        elif problems:
            issues["D"] = {"level": "warn", "kind": "review", "message": problems[0]["message"]}
        elif "/" in d:
            issues["D"] = {"level": "warn", "kind": "format", "message": f"Phôi có {len(d.split('/'))} số — giữ nguyên như phôi"}
    if doc_type == "br":
        if j and not re.fullmatch(r"\d{2}\.\d{3}\.\d{3}/\d{4}-\d{2}", j):
            issues["J"] = {"level": "error", "kind": "format", "message": "CNPJ phải dạng 00.000.000/0000-00"}
        elif j and not cnpj_valid(j):
            issues["J"] = {"level": "error", "kind": "format", "message": "Sai số kiểm tra CNPJ — đối chiếu lại phôi"}
        if h and h not in BR_UF:
            issues["H"] = {"level": "error", "kind": "format", "message": "UF không hợp lệ"}
        if i and not re.fullmatch(r"\d{8}|\d{2}\.\d{3}-\d{3}", i):  # the Sheet keeps the 8 digits
            issues["I"] = {"level": "error", "kind": "format", "message": "CEP phải có 8 chữ số"}
    elif doc_type == "wa":
        # Washington filings: the principal office can be in another state or abroad (Mexico…) → warnings only.
        if i and not re.fullmatch(r"\d{5}(-\d{4})?", i):
            issues["I"] = {"level": "warn", "kind": "format", "message": "Không phải ZIP Mỹ (trụ sở ở nước ngoài?) — đối chiếu phôi"}
        if h and not re.fullmatch(r"[A-Z]{2}", h):
            issues["H"] = {"level": "warn", "kind": "format", "message": "Không phải mã bang 2 chữ — đối chiếu phôi"}
        if j and not re.fullmatch(r"\d{9}", j):
            issues["J"] = {"level": "warn", "kind": "format", "message": "UBI thường có 9 chữ số — đối chiếu lại phôi"}
    elif doc_type in ("wy", "ca"):
        if i and not re.fullmatch(r"\d{5}(-\d{4})?", i):
            issues["I"] = {"level": "error", "kind": "format", "message": "ZIP phải 5 số (hoặc 5+4)"}
        if h and not re.fullmatch(r"[A-Z]{2}", h):
            issues["H"] = {"level": "error", "kind": "format", "message": "Bang phải là mã 2 chữ (vd CA)"}
        if doc_type == "ca" and j and not re.fullmatch(r"\d{12}", j):
            # Only one sample seen: warn, never block.
            issues["J"] = {"level": "warn", "kind": "format", "message": "Mẫu đã thấy có 12 chữ số — kiểm tra lại (không chặn lưu)"}
    # California cross-check against the copy printed on a later page (set by the AI read; gone after a manual edit)
    for k in ("J", "A"):
        chk = (fields.get(k) or {}).get("check")
        if not chk or not val(k) or (issues.get(k) or {}).get("level") == "error":
            continue
        if chk["match"] is False:
            if k == "J":
                issues[k] = {"level": "error", "kind": "format",
                             "message": f"Khác số in lại ở trang sau ({chk['other']}) — đối chiếu PDF rồi sửa tay"}
            else:
                issues[k] = {"level": "warn", "kind": "format", "message": f"Tên ở trang sau ghi “{chk['other']}” — đối chiếu lại"}
        elif chk["match"] is None and k == "J":
            issues[k] = {"level": "warn", "kind": "format", "message": "Không thấy số in lại ở trang sau để đối chiếu — kiểm tra bằng mắt"}
    return issues


def blocking(issues: dict) -> dict:
    return {k: v for k, v in issues.items() if v["level"] == "error"}
