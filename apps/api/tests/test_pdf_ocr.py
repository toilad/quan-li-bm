"""Scanned California filings read by OCR — regression tests with made-up companies (no real data in Git).
The boxes reproduce the layouts and the OCR slips seen on the owner's real scans (2026-10-19): positions in pixels at
300 dpi, as RapidOCR returns them. These are MOCKED inputs: they prove the reading rules, not that the OCR engine reads a
real file — that is checked separately on the real PDFs (tests/test_pdf_ocr_real.py, opt-in)."""
import pytest

from wg_core.modules.pdf.ocr import Box, Page, _respace, extract_ca_scan, identify, suspects

W, H = 2550, 3300


def b(y, x, text, conf=0.97, w=None):
    return Box(x, y, x + (w or 22 * len(text)), y + 40, text, conf)


def page(boxes, i=0):
    p = Page(i, sorted(boxes, key=lambda x: (x.y, x.x)), W, H)
    p.words = " ".join(x.key for x in p.boxes)
    return p


def head(form="LLC-1", title="ARTICLES OF ORGANIZATION", number="201099910123", rev="REV 04/2007"):
    return [b(130, 1650, number), b(170, 1300, form), b(200, 620, "State of California"), b(260, 680, "Secretary of State"),
            b(660, 450, "LIMITED LIABILITY COMPANY"), b(720, 450, title), b(890, 1610, "This Space For Filing Use Only"),
            b(3150, 200, f"{form} ({rev})"), b(700, 2000, "JUL 08 2010")]


def llc1(name_text="Sample Ridge Holdings, LLC", item4=True, return_to=False, name_conf=0.97):
    boxes = head() + [
        b(960, 215, 'ENTITY NAME (End the name with the words "Limited Liability Company," or the abbreviations'),
        b(1070, 220, "1.NAMEOFLIMITEDLIABILITYCOMPANY"), b(1120, 260, name_text, name_conf),
        b(1235, 213, "PURPOSE (The following statement is required by statute"),
        b(1560, 216, "3.NAME OF INITIAL AGENT FOR SERVICE OF PROCESS"), b(1620, 262, "Jane Sample"),
        b(1730, 216, "4.IFANINDMDUAL.ADDRESSDFINITALAGENTFORSERVICEOFPROCESSNCALIFORNIA"), b(1728, 1516, "CITY"),
        b(1727, 1807, "STATE"), b(1730, 1968, "ZIP CODE"), b(1792, 1827, "CA"),
        b(1900, 220, "MANAGEMENT(Checkonlyone)")]
    if item4:
        boxes += [b(1797, 267, "100 W 1st Street , Torrance", 0.93), b(1797, 1968, "90501")]
    if return_to:
        boxes += [b(2700, 173, "RETURN TO (Enter the name and the address of the person or firm"),
                  b(2868, 222, "FIRM"), b(2863, 493, name_text.upper()), b(2940, 220, "ADDRESS"), b(2940, 489, "2725 SAMPLE LEAF AVE"),
                  b(3005, 220, "CITY/STATE/ZIP [ROSEMEAD, CA 91770")]
    return [page(boxes)]


def llc5(item8=False, number="201099910043"):
    boxes = head("LLC-5", "APPLICATION FOR REGISTRATION", number) + [
        b(905, 91, 'ENTITY NAME (End the name in Item 1 with the words "Limited Liability Company."'),
        b(934, 93, "(aaoadsal .oo. pue pl., ol paleiaaqqe", 0.58), b(1085, 143, "500 SAMPLE STREET HOLDINGS, LLC", 0.98),
        b(1170, 90, "2.NAMEOFTHEFOREIGNLIMITEDLIABILITYCOMPANY.IFDIFFERENTFROMTHATENTEREDINITEM1ABOVE"),
        b(1409, 88, "3.THISFOREIGNLIMITEDLIABILITYCOMPANYWASFORMED ON"), b(1407, 1179, "04"), b(1409, 1366, "19"),
        b(1409, 1473, "2010"), b(1421, 1679, "N"), b(1403, 1973, "MARYLAND"),
        b(1734, 95, "4.NAME OFAGENT FOR SERVICE OFPROCESS"), b(1789, 135, "Sample Agent Service Company"),
        b(1888, 93, "5.IFANINDIVIDUAL.ADDRESS OFINITIALAGENT FOR SERVICE OF PROCESSIN CALIFORNIA"),
        b(1887, 1631, "CITY"), b(1887, 1917, "STATE"), b(1887, 2076, "ZIP CODE"), b(1930, 1938, "CA"),
        b(2050, 90, "APPOINTMENT (The following statement is required"),
        b(2330, 90, "7. ADDRESS OF THE PRINCIPAL EXECUTIVE OFFICE"), b(2330, 1640, "CITY AND STATE"), b(2330, 2080, "ZIP CODE"),
        b(2385, 150, "701 13th St. NW, Suite 1000,"), b(2385, 1830, "Washington,"), b(2385, 2075, "DC 20005"),
        b(2470, 90, "8 ADDRESS OF THE PRINCIPAL OFFICE IN CALIFORNIA, IF ANY"), b(2470, 1640, "CITY"), b(2470, 1917, "STATE"),
        b(2470, 2080, "ZIP CODE"), b(2520, 1930, "CA"), b(2620, 90, "EXECUTION")]
    if item8:
        boxes += [b(2525, 150, "5500 Sample Blvd 4th floor - West Wing"), b(2525, 1700, "Los Angeles"), b(2525, 2080, "90028")]
    attach = page([b(400, 300, "SEE ATTACHMENT"), b(3100, 1700, number)], 1)
    # page 3: the home state's certificate — its office address and phone are not the company's
    cert = page([b(300, 600, "State of Maryland"), b(500, 300, "301 W. Preston Street, Baltimore, MD 21201"),
                 b(560, 300, "Phone: (410) 767-1340 Fax: (410) 333-7097"), b(3100, 1700, number)], 2)
    return [page(boxes), attach, cert]


def vals(f):
    return {k: v.get("value", "") for k, v in f.items()}


# ───── form + version are identified first ─────

def test_identify_form_and_version():
    assert identify(llc1()) == {"state": "CA", "form": "LLC-1", "layout": "2007", "version": "LLC-1 REV 04/2007", "verified": True}
    assert identify(llc5())["version"] == "LLC-5 REV 04/2007"
    odd = llc1()
    odd[0].boxes = [x for x in odd[0].boxes if "REV" not in x.text] + [b(3150, 200, "LLC-1 [REV 09/2011)")]
    f, extra = extract_ca_scan(odd)
    assert extra["version"] == "LLC-1 REV 09/2011" and not extra["version_verified"] and "chưa được kiểm chứng" in extra["warning"]
    assert identify([page([b(100, 100, "CERTIFICATE OF EXISTENCE"), b(200, 100, "State of Nevada")])]) is None


# ───── addresses: only the company's own address fills F–I ─────

def test_llc1_old_form_takes_item_4_agent_address_for_f_to_i():
    """Owner, 2026-10-21: LLC-1 REV 03/2005 / 04/2007 have no principal-office box → F–I = item 4 (initial agent's
    address), address_source LLC1_ITEM4."""
    f, extra = extract_ca_scan(llc1())
    v = vals(f)
    assert v["A"] == "Sample Ridge Holdings, LLC" and v["J"] == "201099910123" and v["D"] == ""
    assert (v["F"], v["G"], v["H"], v["I"]) == ("100 W 1st Street, Torrance, CA 90501", "Torrance", "CA", "90501")
    assert f["F"]["role"] == "agent" and extra["address_source"] == "LLC1_ITEM4" and extra["address_candidates"] == []
    assert extra["address_selected"]["source"] == "LLC1_ITEM4" and extra["status"] == "OK"
    assert f["F"]["region"]["page"] == 1 and len(f["F"]["region"]["box"]) == 4
    assert f["A"]["region"]["page"] == 1 and f["A"]["source"] == "ocr" and f["A"]["checked"] is False


def test_llc1_item_4_read_when_the_zip_header_is_missed_and_bivd_is_flagged():
    """30277596: OCR missed the ZIP CODE header — item 4 is still found from its STATE / CITY header, the ZIP taken
    from the "CA 94602" cell. "Bivd." (Blvd.) is flagged for the owner, never corrected."""
    pages = llc1()
    pages[0].boxes = [x for x in pages[0].boxes if x.text not in ("ZIP CODE", "CA", "90501")] + [b(1797, 1827, "CA 90501")]
    f, extra = extract_ca_scan(pages)
    assert (vals(f)["F"], vals(f)["I"], extra["address_source"]) == ("100 W 1st Street, Torrance, CA 90501", "90501", "LLC1_ITEM4")
    pages = llc1()
    for x in pages[0].boxes:
        if x.text.startswith("100 W"):
            x.text = "120 No. Robertson Bivd., 3rd Floor, Torrance"
    f, extra = extract_ca_scan(pages)
    assert "Blvd" in f["F"]["suspects"][0]["suggestion"] and extra["status"] == "REVIEW_REQUIRED"
    assert "Blvd" not in vals(f)["F"]  # the reading itself is left as read
    f, extra = extract_ca_scan(llc1(item4=False))
    assert "ô địa chỉ agent để trống" in extra["extraction_reason"]


def test_llc1_corporate_agent_offers_return_to_and_says_the_firm_is_the_company():
    f, extra = extract_ca_scan(llc1(name_text="SAMPLE HORSE HOLDINGS LLC", item4=False, return_to=True))
    assert vals(f)["F"] == "" and extra["status"] == "NO_BUSINESS_ADDRESS_ON_FORM"  # item 4 blank; Return To never used
    [c] = extra["address_candidates"]
    assert (c["role"], c["street"], c["city"], c["zip"]) == ("return_to", "2725 SAMPLE LEAF AVE", "ROSEMEAD", "91770")
    assert "FIRM là chính công ty này" in extra["note"]


def test_llc5_item_7_in_dc_item_8_blank_certificate_page_ignored():
    """The 38776980 case (made-up values): items 7 and 8 never mixed, the agent never the company, nothing taken from the
    Maryland certificate page, the home state kept apart from the address."""
    f, extra = extract_ca_scan(llc5())
    v = vals(f)
    assert v["A"] == "500 SAMPLE STREET HOLDINGS, LLC" and v["J"] == "201099910043"
    assert v["F"] == "701 13th St. NW, Suite 1000, Washington, DC 20005"
    assert (v["G"], v["H"], v["I"]) == ("Washington", "DC", "20005") and f["F"]["role"] == "principal"
    assert extra["address_candidates"] == []  # item 8 left blank: nothing invented
    assert v["D"] == "" and "không có ô số điện thoại" in f["D"]["note"]  # the certificate's phone is not the company's
    assert extra["formation_state"] == "MARYLAND" and extra["formation_date"] == "04/19/2010" and extra["filed_date"] == "07/08/2010"
    assert extra["agent_name"] == "Sample Agent Service Company" and extra["pages_read"] == 3
    assert f["J"]["check"] == {"other": "201099910043", "match": True}


def test_llc5_item_8_is_a_separate_suggestion():
    f, extra = extract_ca_scan(llc5(item8=True))
    assert vals(f)["F"].startswith("701 13th St. NW")
    [c] = extra["address_candidates"]
    assert c["role"] == "principal_ca" and c["street"] == "5500 Sample Blvd 4th floor - West Wing" and c["city"] == "Los Angeles"


def test_number_differing_on_a_later_page_is_flagged():
    pages = llc5()
    pages[1].boxes[-1] = b(3100, 1700, "201099910048")
    f, _ = extract_ca_scan(pages)
    assert f["J"]["check"] == {"other": "201099910048", "match": False}


# ───── OCR slips are flagged, never corrected silently ─────

def test_handwritten_name_is_left_empty_and_reported():
    f, _ = extract_ca_scan(llc1(name_text="LLC", name_conf=0.91))
    assert f["A"]["value"] == "" and "viết tay" in f["A"]["note"]


def test_suspicious_name_keeps_the_reading_and_flags_it():
    f, _ = extract_ca_scan(llc1(name_text="Sample Hotel Group. LLC."))
    assert f["A"]["value"] == "Sample Hotel Group. LLC."  # unchanged
    assert "dấu phẩy" in f["A"]["suspects"][0]["message"] and f["A"]["suspects"][0]["suggestion"] == "Sample Hotel Group, LLC."


@pytest.mark.parametrize("text, suggestion", [
    ("210 Westboume Street", "Westbourne"),    # rn read as m (seen on a real LLC-5)
    ("JDS Fixnure Co., LLC", "Fixture"),        # tu read as nu (seen on the 2013 LLC-1)
    ("P.O. B0x 3664", "BOx"),                   # zero among letters
    ("1234 E.17TH STREET", "1234 E. 17TH STREET"),  # missing space after a direction
    ("Suite 2O4", "204"),                       # letter O among digits
])
def test_suspects(text, suggestion):
    found = suspects(text)
    assert found and any(suggestion in s["suggestion"] for s in found), found


@pytest.mark.parametrize("text", ["9460 Wilshire Blvd., 7th Floor", "35 Corte Madera Avenue, Suite 7", "HOWARD HOLLOWAY FILMS LLC",
                                  "Holiday GP House, LLC", "2340 W 230th Street"])
def test_no_false_alarm_on_clean_readings(text):
    assert suspects(text) == []


def test_respace_keeps_characters_and_punctuation():
    assert _respace("1000 EastWilliamStreet Suite204", "1000 East William Street Suite 204") == "1000 East William Street Suite 204"
    assert _respace("1234 E.17TH STREET", "1234 E 17TH : STREET") == "1234 E. 17TH STREET"


# ───── Certificate of Limited Partnership (LP-1), layout of the 31230213 scan, made-up values ─────

def lp1():
    boxes = [b(172, 1662, "200799910006"), b(276, 668, "State of California"), b(360, 740, "Secretary of State"),
             b(605, 260, "CERTIFICATE OF LIMITED PARTNERSHIP"), b(832, 1681, "This Space For Filing Use Only"),
             b(893, 151, 'ENTITY NAME (End the name with the words "Limited Partnership"or the abbreviation "L P ")'),
             b(947, 207, "NAME OF LIMITEO PARTNERSHIP"), b(982, 211, "Sample Canyon Housing Group, LP", 0.99),
             b(1049, 148, "PRINCIPAL EXECUTIVE OFFICE ADDRESS (Do not abbreviate the name of the city."),
             b(1105, 207, "STREETADDRESS"), b(1105, 1417, "CITY AND STATE"), b(1108, 2090, "ZIP CODE"),
             b(1149, 214, "100 Sample Vista Blvd., Ste. 640"), b(1149, 1365, "Los Angeles, CA"), b(1151, 2118, "90049"),
             b(1210, 150, "COUNTY INFORMATION (Complete Item 3 only if the limited partnership was formed"),
             b(1556, 207, "NAMEOFAGENTFORSERVICEOFPROCESS"), b(1590, 211, "Sample Agent, Inc."),
             b(1651, 202, "IF AN INDIVIDUAL, ADORESS OF AGENT FOR SERVICE OF PROCESS IN CALIFORNIA"),
             b(1655, 1494, "CITY"), b(1655, 1892, "STATE"), b(1655, 2070, "ZIP CODE"), b(1699, 1928, "CA"),
             b(1755, 146, "GENERAL PARTNERS{Enter the names and addresses of all of the general partners."),
             b(1811, 783, "ADDRESS"), b(1811, 1496, "CITY AND STATE"), b(1812, 2068, "ZIP CODE"),
             b(1847, 1471, "Pasadena, CA"), b(1852, 2100, "91101"), b(1857, 140, "Sample Edge Inc. 9 Partner Way"),
             b(1911, 783, "ADDRESS"), b(1906, 1496, "CITY AND STATE"), b(1911, 2070, "ZIP CODE"),
             b(2311, 153, "EXECUTION"), b(2836, 206, "FIRM"), b(2897, 476, "77 Filing Road"), b(2905, 206, "ADDRESS"),
             b(2974, 452, "[Long Beach, CA 90802"), b(2976, 207, "CITY/STATE/ZIP", w=238), b(3064, 151, "LP-1 (REV 03/2005)")]
    return [page(boxes)]


def test_lp1_principal_executive_office_never_general_partner_agent_or_return_to():
    f, extra = extract_ca_scan(lp1())
    v = vals(f)
    assert extra["version"] == "LP-1 REV 03/2005" and extra["version_verified"]
    assert v["A"] == "Sample Canyon Housing Group, LP" and v["J"] == "200799910006"
    assert (v["G"], v["H"], v["I"]) == ("Los Angeles", "CA", "90049") and f["F"]["street"] == "100 Sample Vista Blvd., Ste. 640"
    roles = {c["role"]: c for c in extra["address_candidates"]}
    assert set(roles) == {"general_partner", "return_to"} and roles["return_to"]["city"] == "Long Beach"
    assert extra["status"] == "OK"


# ───── status per document type; readings never merged silently ─────

def test_status_follows_the_form_not_a_fixed_list():
    from wg_core.modules.pdf.doc_rules import problems

    f, extra = extract_ca_scan(llc1())  # old LLC-1: no business-address box → item 4 (owner, 2026-10-21)
    assert extra["status"] == "OK"
    # item 4 blank (a corporate agent): empty F–I is the right answer
    assert extract_ca_scan(llc1(item4=False))[1]["status"] == "NO_BUSINESS_ADDRESS_ON_FORM"
    pages = llc1()
    pages[0].boxes = [x for x in pages[0].boxes if x.text != "201099910123"]
    f, extra = extract_ca_scan(pages)  # J missing: still usable on a California form
    assert f["J"]["value"] == "" and extra["status"] == "OK"
    assert extract_ca_scan(llc1(name_text="LLC", name_conf=0.91))[1]["status"] == "REVIEW_REQUIRED"
    assert extract_ca_scan(llc1(name_text="Y LLC"))[1]["failure_category"] == "đọc được label nhưng không đọc được value"
    assert problems("br", {"A": {"value": "X LTDA"}, "F": {"value": "RUA A, 1, SAO PAULO, SP 01001000"}, "G": {"value": "SAO PAULO"}, "H": {"value": "SP"},
                           "I": {"value": "01001000"}}) == ["Thiếu J: không đọc được"]
    assert problems("wa", {"A": {"value": "X LLC"}}) == []  # UBI may be missing on a Washington filing


def test_text_layer_and_ocr_disagreeing_goes_to_review_with_both_readings():
    from wg_core.modules.pdf.ocr import scan_report, with_text_layer

    f, extra = extract_ca_scan(lp1())
    with_text_layer(f, extra, {"A": {"value": "Sample Canyon Housing Group, LP"}, "J": {"value": "200799910008"}})
    assert extra["status"] == "REVIEW_REQUIRED" and "200799910008" in extra["extraction_reason"]
    assert f["J"]["value"] == "200799910006"  # the cell is not switched to either side
    assert [r["source"] for r in f["J"]["readings"]] == ["ocr", "text"] and f["A"]["sources_agree"] is True
    rep = scan_report(f, extra)
    assert rep["fields"]["file_number"]["readings"][1] == {"value": "200799910008", "source": "text", "confidence": 100}


def test_read_scan_report_and_the_whole_page_read_once_on_the_original_image(monkeypatch):
    from wg_core.modules.pdf import ocr

    handwritten = lp1()
    handwritten[0].boxes = [x if not x.text.startswith("Sample Canyon") else b(982, 211, "LP", 0.9) for x in handwritten[0].boxes]
    variants = []
    monkeypatch.setattr(ocr, "ocr_document", lambda data, variant="original", **kw: variants.append(variant) or handwritten)
    monkeypatch.setattr(ocr, "reread", lambda *a, **kw: ("", 0.0))
    monkeypatch.setattr(ocr, "reread_many", lambda data, region, dpi=450, variants=("original",): [("", 0.0)] * len(variants))
    monkeypatch.setattr(ocr, "read_band", lambda *a, **kw: ("", 0.0))
    r = ocr.read_scan(b"%PDF")
    assert variants == ["original"]  # owner, 2026-10-20: no image variants of the whole page — only of small field crops
    assert r["status"] == "REVIEW_REQUIRED" and r["entity_name"] == "" and "viết tay" in r["reason"]
    assert set(r) >= {"document_type", "entity_name", "business_address", "file_number", "status", "reason",
                      "selected_candidates", "rejected_candidates", "fields", "sheet"}
    assert r["selected_candidates"][0]["role"] == "principal"
    assert {c["role"] for c in r["rejected_candidates"]} == {"general_partner", "return_to"}
    assert all(set(c) == {"value", "role", "reason"} for c in r["rejected_candidates"])
    street = r["fields"]["business_street"]
    assert street["value"] == "100 Sample Vista Blvd., Ste. 640" and street["source"] == "ocr" and street["page"] == 1
    assert len(street["bbox"]) == 4 and street["confidence"] > 0


# ───── the review screen's API: crops, "đã kiểm tra", suggested addresses, no save before checking ─────

def _ocr_doc(**form):
    """A scanned document as the OCR job leaves it (made-up values) + a one-page PDF on disk for the crops."""
    import hashlib
    import io

    from pypdf import PdfWriter

    from wg_core.db import session_scope
    from wg_core.models import PdfDocument
    from wg_core.modules.pdf.service import storage_path

    buf = io.BytesIO()
    w = PdfWriter()
    w.add_blank_page(612, 792)
    w.write(buf)
    _ocr_doc.n = getattr(_ocr_doc, "n", 0) + 1  # a different file each call (md5 is unique)
    data = buf.getvalue() + f"%test-ocr-{_ocr_doc.n}".encode()
    md5 = hashlib.md5(data).hexdigest()
    storage_path(md5).write_bytes(data)
    fields, extra = extract_ca_scan(llc1(**form))
    with session_scope() as s:
        d = PdfDocument(md5=md5, original_name="scan.pdf", size=len(data), pages=1, has_text=False, doc_type="ca",
                        detection_confidence=0.9, detection_reason="OCR", fields=fields, extra=extra, industry={}, status="review")
        s.add(d)
        s.flush()
        return d.id


def test_cells_read_from_a_scan_cannot_be_saved_before_the_owner_checks_them(client):
    from wg_core.db import session_scope
    from wg_core.models import Job, PdfDocument
    from wg_core.modules.pdf import service as pdf

    doc_id = _ocr_doc(item4=False, return_to=True)
    r = client.post(f"/api/pdf/{doc_id}/save", json={"confirm_missing": False, "critical_checked": True})
    # old LLC-1 with item 4 blank: F–I missing is named (the "Return to" address is never used by itself)
    assert r.status_code == 422 and any(x.startswith("F:") for x in r.json()["detail"]["reasons"])
    with session_scope() as s:
        assert not s.query(Job).filter(Job.kind == "pdf_save").count()  # nothing queued for Drive / the Sheet

    # the region image shown next to a cell
    doc = next(d for d in client.get("/api/pdf").json() if d["id"] == doc_id)
    box = ",".join(str(v) for v in doc["fields"]["A"]["region"]["box"])
    img = client.get(f"/api/pdf/{doc_id}/crop", params={"page": 1, "box": box})
    assert img.status_code == 200 and img.headers["content-type"] == "image/png" and img.content[:4] == b"\x89PNG"

    # the owner picks the suggested address for F–I, then ticks the cells
    r = client.patch(f"/api/pdf/{doc_id}", json={"use_candidate": 0})
    f = r.json()["fields"]
    assert f["F"]["value"].startswith("2725 SAMPLE LEAF AVE, ROSEMEAD") and f["F"]["source"] == "manual" and f["F"]["role"] == "return_to"
    assert f["G"]["value"] == "ROSEMEAD" and f["I"]["value"] == "91770" and f["F"]["checked"] is True
    r = client.patch(f"/api/pdf/{doc_id}", json={"checked": {"A": True, "J": True}})
    assert r.json()["fields"]["A"]["checked"] is True
    with session_scope() as s:
        assert not pdf.save_check(s.get(PdfDocument, doc_id), confirm_missing=True, critical_checked=True)


def test_typing_a_cell_counts_as_checked_and_keeps_its_region(client):
    doc_id = _ocr_doc()
    r = client.patch(f"/api/pdf/{doc_id}", json={"fields": {"A": "Sample Ridge Holdings, LLC"}})
    a = r.json()["fields"]["A"]
    assert a["source"] == "manual" and a["checked"] is True and a["region"]["page"] == 1


# ───── entity name: never a doubtful name as "OK" (owner, 2026-10-20) ─────

@pytest.mark.parametrize("text, kind", [
    ("SAMPLE HOLDINGS.LLC", "suffix"),          # suffix glued to the word
    ("Sample Holdings LL.C", "suffix"),         # odd suffix
    ("KLEIN SAMPLE, LiC", "suffix"),
    ("Sample Holdings", "suffix"),              # no LLC / LP at all
    ("LA SAMPA GUEST HOmE, LLC", "casing"),     # odd casing
    ("Sample Holdings Ill, LLC", "letters"),    # III? Ill?
    ("Hom Away From Hom Sampleton LLC", "letters"),  # a letter possibly missing (lexicon word + 1 letter)
])
def test_name_signals(text, kind):
    from wg_core.modules.pdf.ocr import name_signals

    assert kind in {k for k, _ in name_signals(text)}, name_signals(text)


@pytest.mark.parametrize("text", ["HI Sample Hotel Holdings, LLC", "LINC-Sample Housing Investors, L.P.", "McSample Holdings LLC",
                                  "Sample Brook House Limited Partnership", 'SAMPLE HOUSE LLC ("SH LLC")'])
def test_name_signals_quiet_on_clean_names(text):
    from wg_core.modules.pdf.ocr import name_signals

    assert name_signals(text) == []


def test_purpose_line_is_never_the_name():
    """37948230 case (made-up name): the "PURPOSE (The following statement …)" line under the name is printed text."""
    pages = llc1()
    p = pages[0]
    p.boxes = [x for x in p.boxes if not x.text.startswith("Sample Ridge")]
    p.boxes.append(b(1180, 213, "PLRPOSE (The toltowing statemem l4 requlred by statute and shouid rot be altered.)"))
    p.boxes.sort(key=lambda x: (x.y, x.x))
    f, extra = extract_ca_scan(pages)
    assert f["A"]["value"] == "" and extra["status"] == "REVIEW_REQUIRED"
    p.boxes.append(b(1120, 260, "3400 SAMPLE STREET HOLDING COMPANY, LLC"))
    p.boxes.sort(key=lambda x: (x.y, x.x))
    assert extract_ca_scan(pages)[0]["A"]["value"] == "3400 SAMPLE STREET HOLDING COMPANY, LLC"


def _reads(monkeypatch, at450, at600=None):
    """The 450 dpi second reading, then (only if asked for) the four 600 dpi readings of the name crop."""
    from wg_core.modules.pdf import ocr

    calls, rest = [], list(at600 or [])

    def many(data, region, dpi=450, variants=("original",)):
        calls.append((dpi, variants))
        got, rest[:] = rest[:len(variants)], rest[len(variants):]
        return got

    monkeypatch.setattr(ocr, "reread", lambda *a, **kw: at450)
    monkeypatch.setattr(ocr, "reread_many", many)
    return calls


def test_zoomed_readings_disagreeing_send_the_name_to_review(monkeypatch):
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "Sample Holdings III, LLC", "source": "ocr", "confidence": 99, "region": {"page": 1, "box": [0.1, 0.3, 0.5, 0.32]}}
    calls = _reads(monkeypatch, ("Sample Holdings Ill, LLC", 0.97),
                   [("Sample Holdings Ill, LLC", 0.97)] + [("Sample Holdings III, LLC", 0.98)] * 3)
    check_entity(cell, b"%PDF")
    assert cell["value"] == "Sample Holdings III, LLC" and "khác nhau" in cell["suspects"][0]["message"]
    # 600 dpi: original + gray first; they disagree with the page → sharpen + threshold too (one crop per stage)
    assert calls == [(600, ("original", "gray_contrast")), (600, ("sharpen", "threshold"))]
    assert len(cell["reads"]) == 6 and [r["dpi"] for r in cell["reads"]] == [300, 450, 600, 600, 600, 600]


def test_all_zoomed_readings_agreeing_clearly_are_used_and_said(monkeypatch):
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "Sample Holdings LL.C", "source": "ocr", "confidence": 96, "region": {"page": 1, "box": [0.1, 0.3, 0.5, 0.32]}}
    _reads(monkeypatch, ("Sample Holdings LLC", 0.99), [("Sample Holdings LLC", 0.99)] * 4)
    check_entity(cell, b"%PDF")
    assert cell["value"] == "Sample Holdings LLC" and not cell.get("suspects") and "Sample Holdings LL.C" in cell["note"]


def test_lost_spaces_come_back_from_a_zoomed_reading(monkeypatch):
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "SAMPLE&SAMPLE ENTERPRISES,LLC", "source": "ocr", "confidence": 97, "region": {"page": 1, "box": [0.1, 0.3, 0.5, 0.32]}}
    calls = _reads(monkeypatch, ("SAMPLE & SAMPLE ENTERPRISES, LLC", 0.98), [])
    check_entity(cell, b"%PDF")
    assert cell["value"] == "SAMPLE & SAMPLE ENTERPRISES, LLC" and not cell.get("suspects")
    assert calls == []  # the 450 dpi reading settled it: no 600 dpi crop at all


def test_unstable_readings_keep_the_most_read_candidate_for_review(monkeypatch):
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "iSampleHoll lytvoodHoldings LLC", "source": "ocr", "confidence": 81, "region": {"page": 1, "box": [0.1, 0.3, 0.5, 0.32]}}
    _reads(monkeypatch, ("Samplcy Hollyuvoocd Holdings, LLC", 0.85),
           [("Samplcy Hollyuvoocd Holdings, LLC", 0.85), ("SampleHollyuvood Holdings, LLC", 0.91),
            ("SampleHollyuvood Holdings, LLC", 0.9), ("SamforicHollyuvood Holdings, LLC", 0.9)])
    check_entity(cell, b"%PDF")
    # owner, 2026-10-20: never wipe a candidate — it stays (REVIEW_REQUIRED) so he fixes one letter
    assert cell["value"] in ("Samplcy Hollyuvoocd Holdings, LLC", "SampleHollyuvood Holdings, LLC")  # read twice each
    assert len(cell["unreadable"]) >= 3
    assert "viết tay" in cell["suspects"][0]["message"]


def test_odd_casing_alone_lowers_confidence_never_ok():
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "LA SAMPA GUEST HOmE, LLC", "source": "ocr", "confidence": 99}
    check_entity(cell, None)
    assert cell["confidence"] == 79 and cell["doubts"] and not cell.get("suspects")


# ───── LP-1 REV 01/2010 (designated office only) and LP-5 (foreign LP) ─────

def lp1_2010():
    boxes = [b(79, 1663, "201099900001"), b(128, 1382, "LP-1"), b(202, 479, "State of California"), b(291, 540, "Secretary of State"),
             b(525, 354, "Certificate of Limited Partnership"), b(743, 1729, "This Space For Filing Use Only"),
             b(813, 121, 'Entity Name (End the name with the words "Limited Partnership" or the abbreviation "LP" or "L.P.")'),
             b(885, 118, "1. NAME OF LIMITED PARTNERSHIP"), b(971, 134, "Samplebrook House Limited Partnership"),
             b(1066, 113, "Initial Designated Office Address (Do not abbreviate the name of the city.)"),
             b(1133, 116, "2. ADDRESS OF INITIAL DESIGNATED OFFICE IN CALIFORNIA"), b(1136, 1522, "CITY"), b(1136, 1991, "STATE"),
             b(1136, 2132, "ZIP CODE"), b(1212, 1532, "Los Angeles"), b(1216, 2139, "90048"), b(1217, 2016, "CA"),
             b(1219, 139, "120 Sample Blvd., 3rd Floor"),
             b(1312, 111, "Initial Agent For Service of Process (If the initial agent is an individual"),
             b(1643, 114, "4.IF AN INDIVIDUAL ADDRESS OF INITIAL AGENT FOR SERVICE OF PROCESS IN CA"), b(1643, 1517, "CITY"),
             b(1647, 2084, "ZIP CODE"), b(1648, 1989, "STATE"), b(1727, 2007, "CA"), b(1730, 2137, "90048"),
             b(1732, 139, "120 Sample Blvd., 3rd Floor"), b(1735, 1332, "Los Angeles"),
             b(1816, 109, "General Partners (Enter the names and addresses of all the general partners."),
             b(1891, 835, "ADDRESS"), b(1891, 2124, "ZIP CODE"), b(1893, 113, "6a. NAME"), b(1893, 1986, "STATE"), b(1895, 1520, "CITY"),
             b(1964, 2129, "90048"), b(1966, 1507, "Los Angeles"), b(1968, 2006, "CA"), b(1971, 133, "Jane Sample"),
             b(1974, 770, "120 Sample Blvd., 3rd Flr."), b(2415, 109, "Execution (This certificate must be signed"),
             b(3147, 99, "LP-1 (REV 01/2010)")]
    return [page(boxes)]


def test_lp1_2010_item_2_designated_office_goes_to_f_to_i_before_item_4():
    """Owner, 2026-10-21: LP-1 REV 01/2008 / 01/2010 → F–I = item 2 (initial designated office), item 4 (agent) only
    when item 2 is blank; a general partner never."""
    f, extra = extract_ca_scan(lp1_2010())
    assert extra["version"] == "LP-1 REV 01/2010" and extra["layout"] == "2008"
    assert vals(f)["A"] == "Samplebrook House Limited Partnership"
    assert vals(f)["F"] == "120 Sample Blvd., 3rd Floor, Los Angeles, CA 90048" and f["F"]["role"] == "designated_office"
    assert extra["address_source"] == "LP1_INITIAL_DESIGNATED_OFFICE" and extra["status"] == "OK"
    assert [c["role"] for c in extra["address_candidates"]] == ["agent", "general_partner"]
    pages = lp1_2010()  # item 2 left blank → item 4; the general partner's address is still never used
    pages[0].boxes = [x for x in pages[0].boxes if not 1200 < x.y < 1230]
    for x in pages[0].boxes:
        if 1720 < x.y < 1740:
            x.text = {"120 Sample Blvd., 3rd Floor": "9 Agent Way", "Los Angeles": "Pasadena", "90048": "91101"}.get(x.text, x.text)
    f, extra = extract_ca_scan(pages)
    assert vals(f)["F"] == "9 Agent Way, Pasadena, CA 91101" and extra["address_source"] == "LP1_ITEM4"


def test_lp5_foreign_lp_principal_office():
    boxes = [b(137, 1650, "201099900011"), b(212, 1320, "LP-5"), b(267, 473, "State of California"), b(359, 539, "Secretary of State"),
             b(519, 454, "Foreign Limited Partnership"), b(582, 459, "Application for Registration"),
             b(770, 1683, "This Space For Filing Use Only"), b(833, 184, "Entity Name (See instructions for name requirements)"),
             b(888, 187, "1. NAME OF FOREIGN LIMITED PARTNERSHIP"), b(959, 227, "Sample Hills Hotel LP"),
             b(1026, 206, "ALTERNATE NAME (if the name in Item 1 does not comply"),
             b(1172, 186, "Office Addresses (Please do not abbreviate the name of the city.)"),
             b(1218, 2072, "ZIP CODE"), b(1219, 1922, "STATE"), b(1221, 182, "3.ADDRESS OF PRINCIPAL OFFICE"), b(1221, 1457, "CITY"),
             b(1287, 1462, "Bethesda"), b(1289, 230, "6900 Sample Drive, Suite 1500"), b(1289, 2101, "20817"), b(1290, 1953, "MD"),
             b(1351, 204, ".ADDRESSOFOFFICEREQUIREDINTHEJURISDICTIONOFFORMATION,IFANY"), b(1355, 1458, "CITY"),
             b(1356, 1923, "STATE"), b(1356, 2077, "ZIP CODE"), b(1498, 187, "Date and Place of Organization"),
             b(2068, 187, "General Partners (Enter the names and addresses of all the general partners."),
             b(2160, 1925, "STATE"), b(2162, 186, "8a. NAME"), b(2162, 863, "ADDRESS"), b(2162, 1460, "CITY"), b(2162, 2078, "ZIP CODE"),
             b(2228, 773, "6900 Sample Drive"), b(2230, 1417, "Bethesda"), b(2231, 225, "Sample Hills GP LLC"), b(2231, 2096, "20817"),
             b(2236, 1951, "MD"), b(3022, 187, "LP-5 (REV 01/2010)")]
    f, extra = extract_ca_scan([page(boxes)])
    assert extra["form"] == "LP-5" and extra["version_verified"]
    assert vals(f)["A"] == "Sample Hills Hotel LP"
    assert (vals(f)["G"], vals(f)["H"], vals(f)["I"]) == ("Bethesda", "MD", "20817") and f["F"]["role"] == "principal"
    assert [c["role"] for c in extra["address_candidates"]] == ["general_partner"] and extra["status"] == "OK"


def test_city_starting_left_of_its_header_is_not_glued_to_the_street():
    """A typed city starting left of the CITY AND STATE header (made-up values)."""
    pages = llc5()
    p = pages[0]
    p.boxes = [x for x in p.boxes if x.text not in ("701 13th St. NW, Suite 1000,", "Washington,", "DC 20005")]
    p.boxes += [b(2385, 150, "175 E Sample Ave, #B"), b(2385, 1460, "Sample Valley"), b(2385, 1960, "CA"), b(2385, 2080, "91024")]
    p.boxes.sort(key=lambda x: (x.y, x.x))
    v = vals(extract_ca_scan(pages)[0])
    assert (v["G"], v["H"], v["I"]) == ("Sample Valley", "CA", "91024") and v["F"].startswith("175 E Sample Ave, #B, Sample Valley")


def test_two_600dpi_readings_agreeing_with_the_page_stop_there(monkeypatch):
    from wg_core.modules.pdf.ocr import check_entity

    cell = {"value": "Sample Holdings LLC", "source": "ocr", "confidence": 80, "region": {"page": 1, "box": [0.1, 0.3, 0.5, 0.32]}}
    calls = _reads(monkeypatch, ("Sample Holdings LLC", 0.97), [("Sample Holdings LLC", 0.97)] * 2)
    check_entity(cell, b"%PDF")
    assert calls == [(600, ("original", "gray_contrast"))]  # low confidence → 600 dpi, but no sharpen / threshold needed


def test_name_field_read_alone_when_the_page_ocr_saw_nothing_in_it(monkeypatch):
    """Label misread as "NAME OFLIMIIEO…" and no typed line in the page OCR: the field under the label is OCR'd alone."""
    from wg_core.modules.pdf import ocr

    pages = llc1()
    p = pages[0]
    p.boxes = [x if x.text != "1.NAMEOFLIMITEDLIABILITYCOMPANY" else b(1070, 220, "NAME OFLIMIIEOLIABILITY COMPANY")
               for x in p.boxes if not x.text.startswith("Sample Ridge")]
    monkeypatch.setattr(ocr, "reread", lambda data, region, *a, **kw: ("Sample Ridge Holdings, LLC", 0.97))
    monkeypatch.setattr(ocr, "reread_many", lambda data, region, dpi=450, variants=("original",): [("Sample Ridge Holdings, LLC", 0.97)] * len(variants))
    monkeypatch.setattr(ocr, "read_band", lambda *a, **kw: ("", 0.0))
    f, extra = extract_ca_scan(pages, b"%PDF")
    assert f["A"]["value"] == "Sample Ridge Holdings, LLC" and "vùng ô mục 1" in extra["note"]
