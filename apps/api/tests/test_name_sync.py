"""Column A = the legal name verified on the PDF (owner's rules, 2026-10-19). Fake Sheet (no real Google call)."""
import pytest
import respx

from tests.mocks import FakeSheet
from tests.test_pdf_ocr import _ocr_doc
from wg_core.db import session_scope
from wg_core.integrations.errors import Conflict, Permanent
from wg_core.models import PdfDocument, SheetWrite
from wg_core.modules.pdf import sheet_match as sm


def doc_with(name, j, h, checked=True, source="ocr"):
    doc_id = _ocr_doc()
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        d.fields = {**d.fields, "A": {"value": name, "source": source, "checked": checked, "region": {"page": 1, "box": [0, 0, 1, 1]}},
                    "J": {"value": j, "source": source, "checked": True}, "H": {"value": h, "source": source, "checked": True}}
    return doc_id


def rows():
    return {3: {"A": "Other Company LLC", "H": "WA", "J": "604000001", "B": "other.example", "C": "https://other.example"},
            4: {"A": "Holiday GP House LLC", "H": "CA", "J": "200809410058", "B": "holiday.example", "F": "addr", "K": "Xem phôi"},
            5: {"A": "Same Name, Inc.", "H": "WA", "J": "603 622 707"}}


def run(doc_id, fn):
    sheet = FakeSheet(rows())
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        with session_scope() as s:
            out = fn(s, s.get(PdfDocument, doc_id))
    return out, sheet


def test_same_name_no_update():
    doc_id = doc_with("Same Name, Inc.", "603622707", "WA")  # number written differently in the Sheet: same company
    out, sheet = run(doc_id, lambda s, d: sm.match(d))
    assert out["status"] == "same_name" and [r["row"] for r in out["rows"]] == [5]
    out, sheet = run(doc_id, lambda s, d: sm.rename(s, d, 5, "Same Name, Inc."))
    assert out["changed"] is False and sheet.writes == []


def test_different_name_same_number_and_state_updates_only_that_cell():
    doc_id = doc_with("Holiday GP House, LLC", "200809410058", "CA")
    out, _ = run(doc_id, lambda s, d: sm.match(d))
    assert out["status"] == "name_differs" and out["rows"] == [{"row": 4, "A": "Holiday GP House LLC", "B": "holiday.example", "C": ""}]
    out, sheet = run(doc_id, lambda s, d: sm.rename(s, d, 4, "Holiday GP House LLC"))
    assert out["changed"] and sheet.writes == [("A4", "Holiday GP House, LLC")]  # only A4 — no other row, no other column
    assert sheet.appends == []  # no new row
    assert sheet.rows[4]["B"] == "holiday.example" and sheet.rows[4]["K"] == "Xem phôi" and sheet.rows[3]["A"] == "Other Company LLC"
    with session_scope() as s:
        w = s.query(SheetWrite).filter(SheetWrite.range == "A4").one()
        assert (w.old_value, w.new_value) == ("Holiday GP House LLC", "Holiday GP House, LLC")
        [log] = s.get(PdfDocument, doc_id).extra["renames"]
        assert log["row"] == 4 and log["old"] == "Holiday GP House LLC" and log["read_value"] == "Holiday GP House, LLC"


def test_unverified_ocr_name_is_blocked():
    doc_id = doc_with("Holiday GP I House, LLC 1", "200809410058", "CA", checked=False)
    with session_scope() as s:  # an OCR doubt on the name (two readings)
        d = s.get(PdfDocument, doc_id)
        d.fields = {**d.fields, "A": {**d.fields["A"], "suspects": [{"message": "Hai lần đọc khác nhau", "suggestion": ""}]}}
    out, _ = run(doc_id, lambda s, d: sm.match(d))
    assert out["status"] == "name_differs" and out["name_verified"] is False and "nhiều cách đọc" in out["why"]
    with pytest.raises(Permanent, match="nhiều cách đọc"):
        run(doc_id, lambda s, d: sm.rename(s, d, 4, "Holiday GP House LLC"))


@pytest.mark.parametrize("j, h", [("200809410059", "CA"), ("200809410058", "NV")])
def test_number_or_state_mismatch_never_renames(j, h):
    doc_id = doc_with("Holiday GP House, LLC", j, h)
    out, _ = run(doc_id, lambda s, d: sm.match(d))
    assert out["status"] == "new" and out["rows"] == []
    with pytest.raises(Permanent, match="không đổi tên dòng này"):
        run(doc_id, lambda s, d: sm.rename(s, d, 4, "Holiday GP House LLC"))


def test_a_changed_cell_since_it_was_shown_is_not_overwritten():
    doc_id = doc_with("Holiday GP House, LLC", "200809410058", "CA")
    with pytest.raises(Conflict, match="vừa đổi"):
        run(doc_id, lambda s, d: sm.rename(s, d, 4, "Some older name LLC"))


def test_several_rows_with_the_same_number_are_left_to_the_owner():
    doc_id = doc_with("Holiday GP House, LLC", "200809410058", "CA")
    sheet = FakeSheet({**rows(), 6: {"A": "Holiday GP House", "H": "CA", "J": "200809410058"}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        with session_scope() as s:
            assert sm.match(s.get(PdfDocument, doc_id))["status"] == "ambiguous"
            with pytest.raises(Permanent, match="nhiều dòng"):
                sm.rename(s, s.get(PdfDocument, doc_id), 4, "Holiday GP House LLC")
    assert sheet.writes == []


@pytest.mark.parametrize("a, b, same", [
    ("Acme, LLC", "Acme LLC", False),           # punctuation counts
    ("Acme Inc.", "Acme Inc", False),           # the suffix as printed
    ("Acme L.L.C.", "Acme LLC", False),
    ("Acme  Holdings,  LLC", "Acme Holdings, LLC", True),  # only extra spaces do not count
    ("ACME LLC", "Acme LLC", False),            # case counts too
])
def test_names_with_suffixes_and_punctuation(a, b, same):
    assert sm.same_name(a, b) is same


def test_no_number_or_state_no_match():
    doc_id = doc_with("Holiday GP House, LLC", "", "CA")
    out, _ = run(doc_id, lambda s, d: sm.match(d))
    assert out["status"] == "no_key"


def test_the_api_needs_an_explicit_confirmation(client):
    doc_id = doc_with("Holiday GP House, LLC", "200809410058", "CA")
    sheet = FakeSheet(rows())
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        assert client.get(f"/api/pdf/{doc_id}/sheet-match").json()["status"] == "name_differs"
        r = client.post(f"/api/pdf/{doc_id}/rename", json={"row": 4, "expected_old": "Holiday GP House LLC"})
        assert r.status_code == 422 and sheet.writes == []
        r = client.post(f"/api/pdf/{doc_id}/rename", json={"row": 4, "expected_old": "Holiday GP House LLC", "confirm": True})
        assert r.status_code == 200 and sheet.writes == [("A4", "Holiday GP House, LLC")]


def test_editing_a_keeps_the_first_reading(client):
    doc_id = _ocr_doc()
    r = client.patch(f"/api/pdf/{doc_id}", json={"fields": {"A": "Sample Ridge Holdings, LLC."}})
    a = r.json()["fields"]["A"]
    assert a["value"] == "Sample Ridge Holdings, LLC." and a["read_value"] == "Sample Ridge Holdings, LLC"


def test_drive_file_is_named_after_the_company():
    d = PdfDocument(original_name="38076809-1.pdf", fields={"A": {"value": 'JDS Fixture Co., LLC'}})
    assert sm.drive_name(d) == "JDS Fixture Co., LLC.pdf"
    d.fields = {"A": {"value": 'A/B "C": D?'}}
    assert sm.drive_name(d) == "A B C D.pdf"
    d.fields = {"A": {"value": ""}}
    assert sm.drive_name(d) == "38076809-1.pdf"


def test_a_california_llc1_without_address_is_matched_under_ca():
    doc_id = doc_with("Holiday GP House, LLC", "200809410058", "")
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        d.extra = {**d.extra, "form": "LLC-1", "state_of_form": "CA"}
    out, _ = run(doc_id, lambda s, d: sm.match(d))
    assert out["h"] == "CA" and out["status"] == "name_differs" and out["rows"][0]["row"] == 4


def test_correcting_a_regenerates_the_short_name(client):
    doc_id = _ocr_doc()
    f = client.patch(f"/api/pdf/{doc_id}", json={"fields": {"A": "JDS Fixture Co., LLC"}}).json()["fields"]
    assert f["E"]["value"] == "jdsfixture" and f["E"]["source"] == "auto"  # first 10 characters, like the old app
    client.patch(f"/api/pdf/{doc_id}", json={"fields": {"E": "jdsfix"}})
    f = client.patch(f"/api/pdf/{doc_id}", json={"fields": {"A": "JDS Fixture Co, LLC"}}).json()["fields"]
    assert f["E"]["value"] == "jdsfix"  # typed by the owner: kept


def test_short_name_is_the_first_ten_characters_like_the_old_app():
    from wg_core.modules.pdf.fields import short_name

    assert short_name("MAC ASSISTANCE LTDA") == "macassista"
    assert short_name("J. C. RELOJOARIA LTDA") == "jcrelojoar"
    assert short_name("Hollybrook House Limited Partnership") == "hollybrook"
    assert short_name("Açaí Ltda") == "acailtda"  # shorter names stay whole, accents folded
