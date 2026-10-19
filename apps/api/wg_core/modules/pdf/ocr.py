"""Scanned filings without a text layer, read for free on this machine: RapidOCR (Apache-2.0, ONNX models shipped
inside the package, nothing leaves the computer). Checked on the owner's first 8 California scans (2026-10-19):
LLC-1 (REV 03/2005, 04/2007) and LLC-5 (foreign LLC registration, REV 04/2007).

Every value is read from a known box of the printed form, never guessed; each field keeps the OCR confidence and is
marked source "ocr" so the owner checks it against the page before saving.
"""
import io
import re
from dataclasses import dataclass

from .fields import field, short_name

DPI = 300  # at 200 dpi the words of the LLC-5 run together ("HOMEAMERICAHOLDINGS"); ~15 s per page on this PC
MAX_PAGES = 4
_engine = None


@dataclass
class Box:
    x: float
    y: float
    x2: float
    y2: float
    text: str
    conf: float

    @property
    def key(self) -> str:
        return re.sub(r"[^A-Z0-9]", "", self.text.upper())


def _ocr():
    global _engine
    if _engine is None:
        from rapidocr_onnxruntime import RapidOCR

        _engine = RapidOCR()
    return _engine


def ocr_pages(data: bytes, max_pages: int = MAX_PAGES) -> list[list[Box]]:
    import numpy as np
    import pdfplumber

    pages = []
    with pdfplumber.open(io.BytesIO(data)) as pdf:
        for page in pdf.pages[:max_pages]:
            img = page.to_image(resolution=DPI).original.convert("RGB")
            res, _ = _ocr()(np.array(img))
            boxes = []
            for quad, text, conf in res or []:
                xs, ys = [p[0] for p in quad], [p[1] for p in quad]
                if text.strip():
                    boxes.append(Box(min(xs), min(ys), max(xs), max(ys), text.strip(), float(conf)))
            pages.append(sorted(boxes, key=lambda b: (b.y, b.x)))
    return pages


# ───────────────────────── California LLC-1 / LLC-5 ─────────────────────────

SECTIONS = ("MANAGEMENT", "APPOINTMENT", "OFFICEADDRESSES", "ADDITIONALINFORMATION", "EXECUTION", "PURPOSE", "RETURNTO")
PO_BOX = re.compile(r"^P\.?\s*O\.?\s*BOX\b", re.I)


def _s() -> float:
    """Pixel distances below are measured at 200 dpi."""
    return DPI / 200


def ca_form(pages: list[list[Box]]) -> str | None:
    keys = " ".join(b.key for b in (pages[0] if pages else []))
    if "CALIFORNIA" not in keys or "SECRETARYOFSTATE" not in keys:
        return None
    if "APPLICATIONFORREGISTRATION" in keys or "LLC5" in keys:
        return "LLC-5"
    if "ARTICLESOFORGANIZATION" in keys or "LLC1" in keys:
        return "LLC-1"
    return None


def _label(boxes: list[Box], *keys: str) -> Box | None:
    return next((b for b in boxes if any(k in b.key for k in keys)), None)


def _same_line(boxes: list[Box], ref: Box, *keys: str) -> Box | None:
    return next((b for b in boxes if abs(b.y - ref.y) < 18 * _s() and any(b.key.startswith(k) for k in keys)), None)


def _below(boxes: list[Box], label: Box, depth: float = 75) -> list[Box]:
    """Values typed under a label line: boxes starting below it, above the next printed line, not section titles."""
    return [b for b in boxes if label.y2 - 4 < b.y < label.y2 + depth * _s() and b is not label
            and not b.key.startswith(SECTIONS)]


def _file_number(boxes: list[Box], top: bool = True) -> tuple[str, float]:
    """The 12-digit filing number stamped at the top right (or at the bottom of attachment pages)."""
    cands = [b for b in boxes if 11 <= len(re.sub(r"\D", "", b.text)) <= 13]
    if not cands:
        return "", 0.0
    b = min(cands, key=lambda c: c.y) if top else max(cands, key=lambda c: c.y)
    return re.sub(r"\D", "", b.text), b.conf


def _split_city_state(text: str) -> tuple[str, str]:
    m = re.match(r"^(.*?)[,\s]+([A-Z]{2})[.,!]*$", text.strip())
    return (m.group(1).strip(" ,"), m.group(2)) if m else (text.strip(" ,.!"), "")


def _address_row(boxes: list[Box], head: Box) -> dict | None:
    """Item 4 (LLC-1) / items 5, 7 (LLC-5): street on the left, then the CITY / STATE / ZIP CODE columns of the header."""
    city_h = _same_line(boxes, head, "CITY")
    state_h = _same_line(boxes, head, "STATE")
    zip_h = _same_line(boxes, head, "ZIPCODE", "ZIP")
    vals = _below(boxes, head)
    if not vals:
        return None
    page_w = max(b.x2 for b in boxes)
    city_x = city_h.x - 90 * _s() if city_h else page_w * 0.55  # the CITY header itself is sometimes not read
    out = {"street": [], "city": [], "state": [], "zip": []}
    for b in sorted(vals, key=lambda v: v.x):
        if zip_h and b.x >= zip_h.x - 40 * _s():
            out["zip"].append(b)
        elif state_h and b.x >= state_h.x - 40 * _s() and city_h and not city_h.key.startswith("CITYANDSTATE"):
            out["state"].append(b)
        elif b.x >= city_x:
            out["city"].append(b)
        else:
            out["street"].append(b)
    txt = {k: " ".join(b.text for b in v).strip() for k, v in out.items()}
    confs = [b.conf for v in out.values() for b in v]
    street, city, state, zipc = txt["street"], txt["city"], txt["state"], txt["zip"]
    if city and not state:
        city, state = _split_city_state(city)
    if not city and "," in street:  # "2340 W 230th Street , Torrance": the city typed in the street box
        street, city = (p.strip() for p in street.rsplit(",", 1))
    if not street.strip(" ,"):
        return None  # left blank on the form (e.g. the agent is a corporation)
    return {"street": street.strip(" ,"), "city": city.strip(" ,.!"), "state": re.sub(r"[^A-Z]", "", state.upper()),
            "zip": re.sub(r"[^\d-]", "", zipc), "conf": min(confs) if confs else 0.0}


def _return_to(boxes: list[Box]) -> dict | None:
    """LLC-1 item 8 "RETURN TO": ADDRESS … / CITY/STATE/ZIP … (used when item 4 is blank: the agent is a company)."""
    addr_l = next((b for b in boxes if b.key == "ADDRESS"), None)
    csz_l = next((b for b in boxes if b.key.startswith("CITYSTATEZIP")), None)
    if not addr_l or not csz_l:
        return None
    right = lambda lab: [b for b in boxes if abs(b.y - lab.y) < 18 * _s() and b.x > lab.x2]  # noqa: E731
    sb, cb = right(addr_l), right(csz_l)
    street = " ".join(b.text for b in sb).strip(" [|]")
    glued = re.split(r"ZIP", csz_l.text, maxsplit=1, flags=re.I)[-1] if re.search(r"\d", csz_l.text) else ""  # label + value read as one
    csz = (glued + " " + " ".join(b.text for b in cb)).strip(" [|]L")
    cb = cb or [csz_l]
    m = re.match(r"^\W*(.*?),?\s+([A-Z]{2})\.?\s+(\d{5}(?:-\d{4})?)\W*$", csz.strip())
    if not street or not m:
        return None
    return {"street": street, "city": m.group(1).strip(" ,"), "state": m.group(2), "zip": m.group(3),
            "conf": min(b.conf for b in sb + cb)}


def tidy(text: str) -> str:
    """OCR slips seen on the owner's scans that have only one reading: "Group. LLC" → "Group, LLC" (a period never
    precedes the suffix), "P.O. B0x" → "P.O. Box", "E.17TH" → "E. 17TH"."""
    text = re.sub(r"\.\s+(LLC|L\.L\.C\.?|INC\.?|LTD\.?)(\W*)$", r", \1\2", text, flags=re.I)
    text = re.sub(r"\b(P\.?\s*O\.?\s*)B0X\b", lambda m: m.group(1) + ("BOX" if m.group(0).isupper() else "Box"), text, flags=re.I)
    return re.sub(r"\b([NSEW])\.(\d)", r"\1. \2", text)


US_STATE_NAMES = {"CALIFORNIA": "CA", "NEVADA": "NV", "DELAWARE": "DE", "WASHINGTON": "WA", "OREGON": "OR", "ARIZONA": "AZ",
                  "TEXAS": "TX", "NEW YORK": "NY", "FLORIDA": "FL", "WYOMING": "WY"}


def _above(boxes: list[Box], label: Box, height: float = 70) -> list[Box]:
    """2013+ LLC-1: the typed value sits on the line ABOVE its printed label."""
    return [b for b in boxes if label.y - height * _s() < b.y < label.y - 4 and b.conf >= 0.8]


def _city_state_zip(text: str) -> tuple[str, str, str]:
    """"Vernon, California 90058" / "LOS ANGELES CA 90001" → (city, ST, zip)."""
    m = re.match(r"^\W*(.*?)[,\s]+([A-Za-z .]+?)\.?,?\s+(\d{5}(?:-\d{4})?)\W*$", text.strip())
    if not m:
        return text.strip(), "", ""
    city, state, zipc = m.group(1).strip(" ,"), m.group(2).strip(" .").upper(), m.group(3)
    if state not in US_STATE_NAMES.values():
        # "Vernon, California" → state name; "Los Angeles CA" lands whole in the city part when the comma is missing
        state = US_STATE_NAMES.get(state, state)
    return city, state, zipc


def _llc1_2013(p1: list[Box]) -> tuple[Box | None, dict | None, str]:
    """LLC-1 (REV 2013 and later): ① LLC Name over "Proposed LLC Name"; ③a street + city/state/zip over
    "Initial Street Address of LLC"."""
    name_l = _label(p1, "PROPOSEDLLCNAME")
    name_b = next((b for b in reversed(_above(p1, name_l)) if b.x < name_l.x + 600 * _s()), None) if name_l else None
    street_l = _label(p1, "INITIALSTREETADDRESSOFLLC")
    if not street_l:
        return name_b, None, ""
    vals = _above(p1, street_l)
    page_w = max(b.x2 for b in p1)
    left = [b for b in vals if b.x < page_w * 0.55]
    right = [b for b in vals if b.x >= page_w * 0.55]
    street = re.sub(r"^\W*(?:[③3]\s*)?a\.\s*", "", " ".join(b.text for b in left)).strip()
    city, state, zipc = _city_state_zip(" ".join(b.text for b in right))
    if not street:
        return name_b, None, ""
    addr = {"street": street, "city": city, "state": state, "zip": zipc, "conf": min(b.conf for b in vals)}
    return name_b, addr, "Mục 3a — Initial Street Address of LLC"


def extract_ca_scan(pages: list[list[Box]]) -> tuple[dict, dict] | None:
    form = ca_form(pages)
    if not form:
        return None
    p1 = pages[0]
    j, j_conf = _file_number(p1)
    if form == "LLC-1" and _label(p1, "PROPOSEDLLCNAME", "INITIALSTREETADDRESSOFLLC"):
        name_b, addr, src = _llc1_2013(p1)
        return _fields(pages, "LLC-1 (2013)", j, j_conf, name_b, addr, src)
    # Item 1, the name: the typed line between the "ENTITY NAME" instructions and the next item (the printed label
    # "1. NAME OF …" is sometimes not read by the OCR).
    end = _label(p1, "2NAMEOFTHEFOREIGN", "PURPOSE")
    tops = [b for b in p1 if end and b.y < end.y and b.key.startswith(("ENTITYNAME", "1NAME", "NAMEOFLIMITED", "NAMEUNDERWHICH",
                                                                         "THISSPACEFORFILING"))]
    top = max(tops, key=lambda b: b.y) if tops else None
    cands = [b for b in p1 if top and end and top.y2 < b.y < end.y and b.conf >= 0.8
             and not re.search(r"NAMEOF|NAMEUNDER|ABBREVIAT|RESPECTIVELY|PROPOSESTOREGISTER", b.key)]
    name_b = cands[-1] if cands else None
    # Addresses: the header lines with CITY / STATE / ZIP CODE (found by "ZIP CODE": the item label is often misread)
    heads = [b for b in p1 if b.key.startswith("ZIPCODE") or b.key == "ZIP"]
    if form == "LLC-5":
        head = next((h for h in heads if _same_line(p1, h, "CITYANDSTATE")), None)
        src = "Mục 7 — Address of the principal executive office"
        addr = _address_row(p1, head) if head else None
        if not addr and heads:
            addr, src = _address_row(p1, heads[0]), "Mục 5 — địa chỉ agent (mục 7 không đọc được)"
    else:
        src = "Mục 4 — địa chỉ agent (mẫu LLC-1 không có ô địa chỉ công ty)"
        addr = _address_row(p1, heads[0]) if heads else None
        if not addr:
            addr, src = _return_to(p1), "Mục 8 — Return to (mục 4 để trống vì agent là công ty)"
    return _fields(pages, form, j, j_conf, name_b, addr, src)


def _fields(pages: list[list[Box]], form: str, j: str, j_conf: float, name_b: Box | None, addr: dict | None,
            src: str) -> tuple[dict, dict]:
    p1 = pages[0]
    if addr and PO_BOX.match(addr["street"]):
        src += " · đây là hộp thư P.O. Box, không phải địa chỉ nhà"
    a = addr or {"street": "", "city": "", "state": "", "zip": "", "conf": 0.0}
    a = {**a, "street": tidy(a["street"])}
    if name_b:
        name_b = Box(name_b.x, name_b.y, name_b.x2, name_b.y2, tidy(name_b.text), name_b.conf)
    pct = lambda c: round(c * 100)  # noqa: E731
    ocr_field = lambda v, c, note=None: {**field(v, "ocr", note), "confidence": pct(c)} if v else field("", "missing", note)  # noqa: E731
    fields = {
        "A": ocr_field(name_b.text if name_b else "", name_b.conf if name_b else 0),
        "D": field("", "missing", f"Mẫu {form} không có ô số điện thoại — anh điền tay"),
        "F": ocr_field(", ".join(x for x in (a["street"], a["city"], f'{a["state"]} {a["zip"]}'.strip()) if x), a["conf"],
                       src if addr else "Không đọc được địa chỉ trên phôi — nhập tay"),
        "G": ocr_field(a["city"], a["conf"]),
        "H": ocr_field(a["state"], a["conf"]),
        "I": ocr_field(a["zip"], a["conf"]),
        "J": ocr_field(j, j_conf, "File # góc trên bên phải"),
    }
    # the filing number stamped again at the bottom of attachment pages (LLC-5 certificates of good standing…)
    later = [n for n, _ in (_file_number(p, top=False) for p in pages[1:]) if n]
    if j:
        fields["J"]["check"] = {"other": later[0], "match": later[0] == j} if later else {"other": "", "match": None}
    fields["E"] = field(short_name(fields["A"]["value"]), "auto", "Tự sinh từ A")
    extra = {"form": form, "address_source": src if addr else "", "reader": "OCR RapidOCR (miễn phí, chạy trên máy)",
             "filed": next((b.text for b in p1 if re.fullmatch(r"[A-Z]{3}\s*\d{1,2}\s*\d{4}", b.text.strip())), "")}
    return fields, extra
