"""Giving a company without a printed phone number a number of its own state — a separate step the owner starts from
PDF Manager (wg_core/phones.py has the rules). Only column D changes; nothing is written to the Sheet or a website here.
"""
import re

from sqlalchemy.orm import Session

from ... import write_guard
from ...integrations.errors import NotConfigured, Permanent
from ...models import PdfDocument, PhoneAssignment
from ...phones import US_AREA_CODES, check, country_of, e164, state_of, us_digits


def _state(doc: PdfDocument) -> str:
    return state_of(doc.fields, doc.extra)


def state_source(doc: PdfDocument) -> str:
    if ((doc.fields.get("H") or {}).get("value") or "").strip():
        return "ô H (địa chỉ doanh nghiệp)"
    return "hồ sơ LLC-1: LLC thành lập tại California" if _state(doc) else ""


def _in_sheet() -> set[str]:
    """Numbers already in column D (any company) — a number goes to one company only. Empty when Sheets is not set up."""
    from ...integrations.google import Sheets

    try:
        rows = Sheets().read_rows()
    except Exception:  # noqa: BLE001 — not configured / offline: the database check still applies
        return set()
    return {us_digits(r.cells["D"]) for r in rows if us_digits(r.cells["D"])}


def display(number: str) -> str:
    d = us_digits(number)
    return f"+1 ({d[:3]}) {d[3:6]}-{d[6:]}" if len(d) == 10 else number


def options(s: Session, doc: PdfDocument) -> dict:
    """What can fill D for this company: numbers the owner already has (free) and numbers on sale (a cost)."""
    from ...integrations.phone_provider import PhoneProvider

    state = _state(doc)
    out = {"state": state, "state_from": state_source(doc), "country": country_of(state), "provider": None, "owned": [],
           "available": [], "message": ""}
    if out["country"] != "US":
        out["message"] = ("Chưa biết bang của doanh nghiệp (ô H trống, hồ sơ không cho biết) — anh xác định bang trước" if not state else
                          f"Cấp số tự động hiện chỉ hỗ trợ bang của Mỹ — {state} cần anh xử lý riêng")
        return out
    try:
        p = PhoneProvider()
    except NotConfigured as e:
        out["message"] = f"{e} — vào Cài đặt API › Số điện thoại để nhập; chưa có thì ô D để trống (needs_setup)"
        return out
    out["provider"] = p.name
    used = {a.number for a in s.query(PhoneAssignment)} | {f"+1{n}" for n in _in_sheet() if len(n) == 10}
    for n in p.owned():
        problems = check(n["number"], state, provisioned=True)
        out["owned"].append({**n, "display": display(n["number"]), "in_use": n["number"] in used,
                             "problems": [x["message"] for x in problems if x["level"] == "error"]})
    out["available"] = [{**n, "display": display(n["number"]), "cost": True} for n in p.available(state)
                        if n["region"].upper() == state and not check(n["number"], state, provisioned=True)]
    if not any(not o["in_use"] and not o["problems"] for o in out["owned"]):
        out["message"] = (f"Tài khoản {p.name} của anh chưa có số trống mã vùng {state} "
                          f"({', '.join(sorted(US_AREA_CODES.get(state, [])) or '?')}) — mua số là bước có phí, cần anh duyệt")
    return out


def assign(s: Session, doc: PdfDocument, number: str, buy: bool = False, confirm_cost: bool = False) -> dict:
    """Put one of the owner's numbers in D (or buy one first, when the owner confirmed the cost). Returns field D."""
    from ...integrations.phone_provider import PhoneProvider

    state = _state(doc)
    number = e164(number, state)
    if country_of(state) != "US" or not number:
        raise Permanent("Chỉ gán được số Mỹ hợp lệ cho doanh nghiệp có bang (ô H) của Mỹ")
    errors = [p["message"] for p in check(number, state, provisioned=True) if p["level"] == "error"]
    if errors:
        raise Permanent(f"Số {display(number)} không dùng được cho {state}: {errors[0]}")
    if s.get(PhoneAssignment, number) or re.sub(r"\D", "", number)[1:] in _in_sheet():
        raise Permanent(f"Số {display(number)} đã dùng cho một doanh nghiệp khác — mỗi số chỉ cho một doanh nghiệp")
    p = PhoneProvider()
    if buy:
        if not confirm_cost:
            raise Permanent("Mua số là bước có phí — cần anh xác nhận phí cho đúng số này")
        try:
            got = p.buy(number, (doc.fields.get("A") or {}).get("value", ""))
        finally:
            write_guard.relock(s, f"Tự khoá sau khi mua số {display(number)}")  # one purchase per opening
        number = got["number"]
    elif number not in {n["number"] for n in p.owned()}:
        raise Permanent(f"Số {display(number)} không có trong tài khoản {p.name} của anh")
    s.add(PhoneAssignment(number=number, doc_id=doc.id, state=state, bought=buy))
    d = {"value": display(number), "source": "provisioned", "phone_source": "provisioned", "checked": True,
         "provider": p.name, "verified_active": False,
         "note": f"Số trong tài khoản {p.name} của anh, mã vùng {us_digits(number)[:3]} ({state}) — chưa gọi thử, chưa xác minh đang hoạt động"}
    doc.fields = {**doc.fields, "D": d}
    return d
