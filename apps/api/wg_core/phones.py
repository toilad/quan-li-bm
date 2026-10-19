"""Business phone numbers (column D) — owner's rules, 2026-10-19:

1. a number printed on the PDF is read and kept exactly as printed (phone_source "source_pdf");
2. no number on the PDF → the company's state is taken from the document, and a number with a matching area code is
   assigned from the owner's own phone provider account (phone_source "provisioned") — never made up;
3. no provider configured / no matching number yet → phone_source "needs_setup", the cell stays empty and the owner is
   told; no placeholder number ever goes to the Sheet or a website;
4. before anything is written: format, area code and state are checked; a number is never reported as working until
   it was verified;
5. getting a number is a separate step; buying one (a cost) needs the owner's explicit go.

The owner typing a number himself is kept apart too (phone_source "manual").
"""
import re

# Area codes per state, kept to the states seen in the owner's data. Overlay codes are added over time: a code not in
# this list is reported as "not in the list" (a warning to check), never silently accepted or rejected.
US_AREA_CODES: dict[str, set[str]] = {
    "WA": {"206", "253", "360", "425", "509", "564"},
    "OR": {"458", "503", "541", "971"},
    "CA": {"209", "213", "279", "310", "323", "341", "350", "408", "415", "424", "442", "510", "530", "559", "562", "619",
           "626", "628", "650", "657", "661", "669", "707", "714", "747", "760", "805", "818", "820", "831", "840", "858",
           "909", "916", "925", "949", "951"},
    "NV": {"702", "725", "775"},
    "FL": {"239", "305", "321", "352", "386", "407", "448", "561", "656", "689", "727", "754", "772", "786", "813", "850",
           "863", "904", "941", "954"},
    "DC": {"202", "771"},
    "MD": {"240", "301", "410", "443", "667"},
    "WY": {"307"},
}
US_STATES = set(US_AREA_CODES) | set(
    "AL AK AZ AR CO CT DE GA HI ID IL IN IA KS KY LA ME MA MI MN MS MO MT NE NH NJ NM NY NC ND OH OK PA RI SC SD TN TX UT "
    "VT VA WV WI".split())
# Brazil: DDD (2 digits) → UF
BR_DDD: dict[str, str] = {
    **{str(d): "SP" for d in range(11, 20)}, "21": "RJ", "22": "RJ", "24": "RJ", "27": "ES", "28": "ES",
    **{str(d): "MG" for d in (31, 32, 33, 34, 35, 37, 38)}, **{str(d): "PR" for d in (41, 42, 43, 44, 45, 46)},
    "47": "SC", "48": "SC", "49": "SC", "51": "RS", "53": "RS", "54": "RS", "55": "RS", "61": "DF", "62": "GO", "64": "GO",
    "63": "TO", "65": "MT", "66": "MT", "67": "MS", "68": "AC", "69": "RO", "71": "BA", "73": "BA", "74": "BA", "75": "BA",
    "77": "BA", "79": "SE", "81": "PE", "87": "PE", "82": "AL", "83": "PB", "84": "RN", "85": "CE", "88": "CE", "86": "PI",
    "89": "PI", "91": "PA", "93": "PA", "94": "PA", "92": "AM", "97": "AM", "95": "RR", "96": "AP", "98": "MA", "99": "MA",
}
BR_UF = set(BR_DDD.values())

SOURCES = {
    "source_pdf": "Số in trên PDF",
    "provisioned": "Số được cấp từ nhà cung cấp của anh",
    "needs_setup": "Chưa có số — cần cấp từ nhà cung cấp",
    "manual": "Anh nhập tay",
}


def country_of(state: str) -> str:
    s = (state or "").strip().upper()
    return "BR" if s in BR_UF and s not in US_STATES else "US" if s in US_STATES else ""


def us_digits(number: str) -> str:
    d = re.sub(r"\D", "", number or "")
    return d[1:] if len(d) == 11 and d.startswith("1") else d


def e164(number: str, state: str) -> str:
    c = country_of(state)
    if c == "US":
        d = us_digits(number)
        return f"+1{d}" if len(d) == 10 else ""
    if c == "BR":
        d = re.sub(r"\D", "", number or "")
        d = d[2:] if d.startswith("55") and len(d) in (12, 13) else d
        return f"+55{d}" if len(d) in (10, 11) else ""
    return ""


def check(number: str, state: str, provisioned: bool = False) -> list[dict]:
    """Problems of one number for a company in `state`: [{level: error|warn, message}]. Empty list = fine."""
    out: list[dict] = []
    if not (number or "").strip():
        return out
    state = (state or "").strip().upper()
    country = country_of(state)
    first = number.split("/")[0]
    if country == "US":
        d = us_digits(first)
        if len(d) != 10:
            return [{"level": "error", "message": "Số Mỹ phải có 10 chữ số (có thể thêm 1 ở đầu)"}]
        npa, nxx = d[:3], d[3:6]
        if npa[0] in "01" or nxx[0] in "01" or npa[1:] == "11":
            return [{"level": "error", "message": f"Mã vùng / đầu số không hợp lệ theo chuẩn Bắc Mỹ ({npa}-{nxx})"}]
        if nxx == "555":
            return [{"level": "error", "message": f"Đầu số 555 là số dành cho phim ảnh / ví dụ — không phải số doanh nghiệp thật"}]
        codes = US_AREA_CODES.get(state)
        if codes is None:
            out.append({"level": "warn", "message": f"Chưa có bảng mã vùng của bang {state} — chưa đối chiếu được mã {npa}"})
        elif npa not in codes:
            out.append({"level": "error" if provisioned else "warn",
                        "message": f"Mã vùng {npa} không thuộc bang {state} (mã của {state}: {', '.join(sorted(codes))})"})
    elif country == "BR":
        d = re.sub(r"\D", "", first)
        d = d[2:] if d.startswith("55") and len(d) in (12, 13) else d
        if len(d) not in (10, 11):
            return [{"level": "error", "message": "Số Brazil phải có DDD + 8 hoặc 9 chữ số"}]
        uf = BR_DDD.get(d[:2])
        if not uf:
            out.append({"level": "error", "message": f"DDD {d[:2]} không tồn tại"})
        elif uf != state:
            out.append({"level": "error" if provisioned else "warn", "message": f"DDD {d[:2]} thuộc {uf}, không phải {state}"})
    else:
        out.append({"level": "warn", "message": f"Chưa biết bang / UF của doanh nghiệp ({state or 'trống'}) — chưa đối chiếu được mã vùng"})
    return out


def tag(fields: dict) -> None:
    """Mark where the number in D came from, right after a document is read."""
    d = fields.get("D")
    if not isinstance(d, dict):
        return
    state = ((fields.get("H") or {}).get("value") or "").upper()
    if d.get("value"):
        d["phone_source"] = "source_pdf"
    else:
        d["phone_source"] = "needs_setup"
        where = f"bang {state}" if state else "bang của doanh nghiệp (chưa có ô H)"
        d["note"] = (d.get("note") + " · " if d.get("note") else "") + \
            f"Phôi không có số — cần cấp số có mã vùng của {where} từ nhà cung cấp của anh; không tự điền số"


def website_phone(number: str, state: str) -> tuple[str, str]:
    """(number to show on a website, reason when hidden). A number that fails the checks is never published."""
    if not (number or "").strip():
        return "", ""
    errors = [p["message"] for p in check(number, state) if p["level"] == "error"]
    return ("", errors[0]) if errors else (number, "")
