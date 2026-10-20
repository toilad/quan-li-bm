"""AUTO_SAVE_TO_SHEET (owner, 2026-10-20): read → straight into the Sheet like the old app. Fake Sheet / Drive only —
no real write. Documents are real BR samples (test-fixtures, gitignored) or made-up cells."""
import pytest
import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, install_drive
from tests.test_pdf import BR, needs_fixtures

from wg_core.db import session_scope
from wg_core.models import Job, PdfDocument
from wg_core.modules.pdf import service as pdf
from wg_core.modules.pdf.fields import field


@pytest.fixture
def auto_on(monkeypatch):
    monkeypatch.setenv("AUTO_SAVE_TO_SHEET", "true")
    monkeypatch.setenv("MANUAL_REVIEW_MODE", "false")


@needs_fixtures
def test_ok_reading_goes_straight_to_the_sheet_full_address_in_f(auto_on):
    data = open(BR[0], "rb").read()
    sheet = FakeSheet({})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m)
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "doc.pdf", data)
            assert doc.extra["status"] == "OK" and doc.status == "queued" and doc.extra["auto_save"] == "queued"
            doc_id = doc.id
        drain()
    with session_scope() as s:
        doc = s.get(PdfDocument, doc_id)
        assert doc.status == "saved" and doc.sheet_row
        row = sheet.appends[0]
        f, g, h, i, j = (doc.fields[k]["value"] for k in "FGHIJ")
        assert row[5:10] == [f, g, h, i, j]  # F full address, G city, H state, I ZIP, J number
        assert f.endswith(f"{g}, {h} {i}")
    from tests.mocks import SHARES
    # the K link opens for anyone who has it — view only, not listed in search (owner, 2026-10-20)
    assert SHARES == [("DRIVE123", {"type": "anyone", "role": "reader", "allowFileDiscovery": False})]


@needs_fixtures
def test_manual_review_mode_stops_every_file(auto_on, monkeypatch):
    monkeypatch.setenv("MANUAL_REVIEW_MODE", "true")
    with session_scope() as s:
        doc, _ = pdf.ingest(s, "doc.pdf", open(BR[0], "rb").read())
        assert doc.status == "review" and "auto_save" not in doc.extra
        assert s.query(Job).filter(Job.kind == "pdf_save").count() == 0


def _doc(status: str, **cells) -> PdfDocument:
    fields = {k: field(v, "ocr") for k, v in {"A": "Sample Holdings, LLC", "D": "", "E": "sampleholdingsllc",
                                               "J": "201099900001", **cells}.items()}
    fields["D"] = {"value": "(213) 555-0123", "source": "auto", "phone_source": "placeholder", "state": "CA"}
    return PdfDocument(md5="x", original_name="x.pdf", size=1, doc_type="ca", status="review", fields=fields,
                       extra={"status": status})


def test_auto_save_rules(auto_on, monkeypatch):
    queued = []
    monkeypatch.setattr(pdf, "request_save", lambda s, d: queued.append(d))
    full = {"F": "1 Sample St, Los Angeles, CA 90001", "G": "Los Angeles", "H": "CA", "I": "90001"}
    assert pdf.auto_save(None, _doc("OK", **full)) == "saved"
    # a form without a business-address box: saved with F–I empty, nothing looked up elsewhere
    assert pdf.auto_save(None, _doc("NO_BUSINESS_ADDRESS_ON_FORM", F="", G="", H="", I="")) == "saved"
    assert len(queued) == 2
    # never guessed: these stay for the owner / are skipped, the batch goes on
    assert pdf.auto_save(None, _doc("REVIEW_REQUIRED", **full)) == "review"
    assert pdf.auto_save(None, _doc("UNKNOWN_DOCUMENT")) == "skipped"
    assert pdf.auto_save(None, _doc("OCR_FAILED")) == "skipped"
    # "OK" but a cell still doubtful, or F not holding G/H/I: not written
    doubtful = _doc("OK", **full)
    doubtful.fields["A"]["suspects"] = [{"message": "III / Ill", "suggestion": ""}]
    assert pdf.auto_save(None, doubtful) == "review" and "A" in doubtful.extra["auto_save"]
    assert pdf.auto_save(None, _doc("OK", **{**full, "F": "1 Sample St"})) == "review"  # F must be the full address
    assert len(queued) == 2
    monkeypatch.setenv("AUTO_SAVE_TO_SHEET", "false")
    assert pdf.auto_save(None, _doc("OK", **full)) == "manual"
