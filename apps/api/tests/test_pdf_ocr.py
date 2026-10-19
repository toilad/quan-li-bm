"""California LLC-1 / LLC-5 scans read by OCR (RapidOCR on this machine). The boxes below copy the positions and the
misreadings RapidOCR produced at 300 dpi on the owner's real scans (2026-10-19); companies and numbers are made up."""
import pytest

from wg_core.modules.pdf.ocr import Box, extract_ca_scan, tidy

S = 1.5  # positions measured at 200 dpi, the reader works at 300


def b(y, x, text, conf=0.97):
    return Box(x * S, y * S, x * S + 12 * len(text), y * S + 20 * S, text, conf)


HEAD = [b(178, 1007, "201099910123"), b(224, 868, "LLC-1"), b(265, 410, "State of California"),
        b(319, 450, "Secretary of State"), b(442, 299, "LIMITED LIABILITY COMPANY"), b(482, 296, "ARTICLES OF ORGANIZATION"),
        b(594, 1077, "This Space For Filing Use Only")]


def values(pages):
    f, extra = extract_ca_scan(pages)
    return {k: v["value"] for k, v in f.items()} | {"_src": extra["address_source"], "_form": extra["form"]}, f


def test_llc1_individual_agent_city_typed_in_the_street_box_and_misread_labels():
    page = HEAD + [
        b(640, 143, 'ENTiTY NAME (End the name with the words "Limited Liabity Company," or the abbreviations'),
        b(713, 147, "1.NAMEOFLIMITEDLIABILITYCOMPANY"), b(746, 174, "Sample Ridge Holdings. LLC"),
        b(823, 142, "PURPOSE (The following statemonl is required by statute"),
        b(1153, 144, "4.IFANINDMDUAL.ADDRESSDFINITALAGENTFORSERVICEOFPROCESSNCALIFORNIA"), b(1152, 1011, "CITY"),
        b(1151, 1205, "STATE"), b(1153, 1312, "ZIP CODE"),
        b(1198, 178, "100 W 1st Street , Torrance", 0.93), b(1195, 1218, "CA"), b(1198, 1312, "90501"),
        b(1267, 147, "MANAGEMENT(Checkonlyone)")]
    v, f = values([page])
    assert v["_form"] == "LLC-1" and v["J"] == "201099910123"
    assert v["A"] == "Sample Ridge Holdings, LLC"  # "Holdings. LLC" is an OCR slip: a period never precedes the suffix
    assert (v["F"], v["G"], v["H"], v["I"]) == ("100 W 1st Street, Torrance, CA 90501", "Torrance", "CA", "90501")
    assert "Mục 4" in v["_src"] and v["D"] == "" and "không có ô số điện thoại" in f["D"]["note"]
    assert f["F"]["source"] == "ocr" and f["F"]["confidence"] == 93
    assert f["J"]["check"] == {"other": "", "match": None}


def test_llc1_corporate_agent_uses_the_return_to_block_even_when_the_label_and_value_are_read_together():
    page = [x for x in HEAD if x.text != "This Space For Filing Use Only"] + [
        b(674, 179, "1. NAME OF LIMITED LIABILITY COMPANY"), b(718, 231, "SAMPLE HORSE HOLDINGS LLC"),
        b(769, 171, "PURPOSE (The following statement is required by statute"),
        b(1153, 144, "4. IF AN INDIVIDUAL, ADDRESS OF INITIAL AGENT"), b(1152, 1011, "CITY"), b(1151, 1205, "STATE"),
        b(1153, 1312, "ZIP CODE"), b(1195, 1218, "CA"),
        b(1267, 147, "MANAGEMENT (Check only one)"),
        b(1960, 220, "ADDRESS"), b(1960, 489, "2725 SAMPLE LEAF AVE"), b(2003, 220, "CITY/STATE/ZIP [ROSEMEAD, CA 91770")]
    v, _ = values([page])
    assert v["A"] == "SAMPLE HORSE HOLDINGS LLC"
    assert v["F"] == "2725 SAMPLE LEAF AVE, ROSEMEAD, CA 91770" and "Return to" in v["_src"]


def test_llc5_principal_office_and_the_number_repeated_on_the_certificate_page():
    page = [b(60, 1000, "200999910076"), b(62, 790, "LLC-5"), b(110, 420, "State of California"),
            b(150, 450, "Secretary of State"), b(300, 180, "APPLICATION FOR REGISTRATION"),
            b(605, 61, 'ENTITY NAME (End the name in Item 1 with the words "Limited Liabilily Company."'),
            b(623, 62, "(aaoadsal .oo. pue pl., ol paleiaaqqe", 0.58), b(723, 95, "SAMPLE AMERICA HOLDINGS, LLC", 0.94),
            b(780, 60, "2.NAMEOFTHEFOREIGNLIMITEDLIABILITYCOMPANY.IFDIFFERENTFROMTHATENTEREDINITEM1ABOVE"),
            b(1267, 62, "5.IFANINDIVIDUAL.ADDRESS OFINITIALAGENT"), b(1267, 1405, "ZIP CODE"),
            b(1298, 1115, "SANTA ANA CA", 0.92), b(1305, 90, "99 E.17TH STREET"), b(1303, 1405, "92701"),
            b(1380, 60, "APPOINTMENT (The following statement"),
            b(1580, 60, "7. ADDRESS OF THE PRINCIPAL EXECUTIVE OFFICE"), b(1580, 1080, "CITY AND STATE"), b(1580, 1405, "ZIP CODE"),
            b(1615, 90, "500 Sample Street"), b(1615, 1160, "La Jolla CA.!"), b(1615, 1405, "92037"),
            b(1700, 60, "8 ADDRESS OF THE PRINCIPAL OFFICE IN CALIFORNIA, IF ANY")]
    cert = [b(400, 300, "CERTIFICATE OF EXISTENCE"), b(2000, 1100, "200999910076")]
    v, f = values([page, cert])
    assert v["_form"] == "LLC-5" and v["A"] == "SAMPLE AMERICA HOLDINGS, LLC"
    assert v["F"] == "500 Sample Street, La Jolla, CA 92037" and "Mục 7" in v["_src"]
    assert f["J"]["check"] == {"other": "200999910076", "match": True}


def test_not_a_california_form():
    assert extract_ca_scan([[b(100, 100, "CERTIFICATE OF EXISTENCE"), b(200, 100, "State of Nevada")]]) is None


@pytest.mark.parametrize("raw, fixed", [("Hollywood Group. LLC.", "Hollywood Group, LLC."), ("P.O. B0x 3664", "P.O. Box 3664"),
                                        ("1234 E.17TH STREET", "1234 E. 17TH STREET"), ("Sample, LLC", "Sample, LLC")])
def test_tidy(raw, fixed):
    assert tidy(raw) == fixed
