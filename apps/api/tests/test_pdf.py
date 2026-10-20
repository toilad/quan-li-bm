import glob
import hashlib
import re
import json

import pytest
import respx
from tests.conftest import FIXTURES, drain
from tests.mocks import FakeSheet, install_drive

from wg_core.db import session_scope
from wg_core.models import Job, PdfDocument, SheetWrite
from wg_core.modules.pdf import service as pdf
from wg_core.modules.pdf.extract import detect, extract_br, read_pdf
from wg_core.modules.pdf.fields import cnpj_valid, short_name, validate

# Real sample filings live only in test-fixtures/ (gitignored). They are sorted by what they are, not by file name,
# and the expected values come from test-fixtures/expected.local.json (also gitignored), keyed by md5.
def _classify():
    br, scans = [], []
    for p in sorted(glob.glob(str(FIXTURES / "*.pdf"))):
        t = read_pdf(open(p, "rb").read())
        (br if detect(t).doc_type == "br" else scans if not t.text.strip() else []).append(p)
    return br, scans


BR, CA = _classify()
EXPECTED_FILE = FIXTURES.parent / "expected.local.json"
EXPECTED = json.loads(EXPECTED_FILE.read_text(encoding="utf-8")) if EXPECTED_FILE.exists() else {}
needs_fixtures = pytest.mark.skipif(not BR, reason="test-fixtures/pdf not present (kept out of Git)")


@needs_fixtures
def test_brazil_detect_and_extract_all_samples():
    for p in BR:
        t = read_pdf(open(p, "rb").read())
        assert detect(t).doc_type == "br"
        f, extra = extract_br(t)
        assert f["A"]["value"] and f["A"]["source"] == "text"
        assert cnpj_valid(f["J"]["value"]), f["J"]
        assert f["H"]["value"] in {"SP", "MG", "RS"}
        assert re.fullmatch(r"\d{8}", f["I"]["value"])  # the Sheet keeps the CEP digits (as text: leading zero kept)
        assert f["F"]["value"].endswith(f'{f["G"]["value"]}, {f["H"]["value"]} {f["I"]["value"]}') and "*" not in f["F"]["value"]
        assert extra["situacao_cadastral"] == "ATIVA"
        assert not {k for k, v in validate(f, "br").items() if v["level"] == "error"}


@pytest.mark.skipif(not EXPECTED, reason="test-fixtures/expected.local.json not present (kept out of Git)")
def test_brazil_exact_values_against_checked_expectations():
    """Every Brazil sample: A, D–J and the main CNAE exactly as checked by eye against the printed comprovante."""
    checked = 0
    for p in BR:
        data = open(p, "rb").read()
        exp = EXPECTED.get(hashlib.md5(data).hexdigest())
        if not exp or exp["doc_type"] != "br":
            continue
        f, extra = extract_br(read_pdf(data))
        for k in "ADFGHIJ":
            assert f[k]["value"] == exp[k], (k, f[k]["value"], exp[k])
        # E: the old app's rule (owner, 2026-10-20) — first 10 characters of A, not the older free-form E in the key
        assert f["E"]["value"] == short_name(exp["A"])
        assert extra["cnae_principal"].startswith(exp["cnae_principal_code"])
        checked += 1
    assert checked == len(BR)


@pytest.mark.skipif(not CA, reason="California sample not present")
def test_california_scan_is_not_guessed():
    t = read_pdf(open(CA[0], "rb").read())
    d = detect(t)
    assert d.doc_type == "unknown" and "scan" in d.reason  # no text layer → owner picks type → AI reads


def test_cnpj_checksum():
    assert cnpj_valid("11.222.333/0001-81")  # public example number, not a real filing
    assert not cnpj_valid("11.222.333/0001-82")


@needs_fixtures
def test_ingest_dedupes_same_bytes():
    data = open(BR[0], "rb").read()
    with session_scope() as s:
        a, new_a = pdf.ingest(s, "a.pdf", data)
        b, new_b = pdf.ingest(s, "copy.pdf", data)
        assert new_a and not new_b and a.id == b.id
        assert a.status == "review" and a.industry["source"] == "doc"


@needs_fixtures
def test_save_flow_drive_then_sheet_and_resume_after_sheet_error():
    data = open(BR[0], "rb").read()
    sheet = FakeSheet({3: {"A": "Existing Co", "B": "x.example.com", "H": "WY", "J": "2024-1"}})
    drive_calls = []
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m, fail_append=1)  # first Sheet write fails
        install_drive(m, calls=drive_calls)
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "doc.pdf", data)
            assert not pdf.save_check(doc, confirm_missing=True, critical_checked=False)
            company = doc.fields["A"]["value"]
            job, _ = pdf.request_save(s, doc)
            doc_id, job_id = doc.id, job.id
        drain()
        with session_scope() as s:
            job, doc = s.get(Job, job_id), s.get(PdfDocument, doc_id)
            assert job.status == "queued" and doc.drive_file_id == "DRIVE123" and not doc.sheet_row  # waiting to retry Sheet only
            job.run_after = job.created_at  # due now
        drain()
        with session_scope() as s:
            job, doc = s.get(Job, job_id), s.get(PdfDocument, doc_id)
            assert job.status == "done" and doc.status == "saved" and doc.sheet_row == 4
            assert s.query(SheetWrite).count() == 2  # the row (A, D–K) + K as “Xem phôi” link
    assert len(drive_calls) == 1  # never uploaded twice
    meta = json.loads(re.search(rb"application/json; charset=UTF-8\r\n\r\n(\{.*?\})\r\n", drive_calls[0].content).group(1))
    # named after the company, not "doc.pdf"; "/" (not allowed in Windows file names) becomes a space
    assert meta["name"] == company.replace("/", " ") + ".pdf"
    row = sheet.appends[0]
    assert row[1] == "" and row[2] == ""  # B, C empty
    assert row[10] == "https://drive.google.com/file/d/DRIVE123/view"  # K first written as the plain link…
    # …then "Xem phôi" linked to the PDF (not a HYPERLINK formula: it breaks in a vi_VN Sheet)
    assert sheet.writes[-1] == ("K4", "Xem phôi → https://drive.google.com/file/d/DRIVE123/view")
    assert sheet.rows[4]["K"] == "Xem phôi" and sheet.links["K4"] == "https://drive.google.com/file/d/DRIVE123/view"
    assert len(row) == 11  # A..K, L untouched
    assert row[9] == doc.fields["J"]["value"]


@needs_fixtures
def test_md5_mismatch_stops_before_sheet():
    data = open(BR[0], "rb").read()
    sheet = FakeSheet({})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m, md5_of=lambda body: "0" * 32)
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "doc.pdf", data)
            job, _ = pdf.request_save(s, doc)
            job_id = job.id
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "failed"
    assert sheet.appends == []


@needs_fixtures
def test_duplicate_in_sheet_is_not_appended():
    data = open(BR[0], "rb").read()
    with session_scope() as s:
        doc, _ = pdf.ingest(s, "doc.pdf", data)
        j, h = doc.fields["J"]["value"], doc.fields["H"]["value"]
    sheet = FakeSheet({3: {"A": "Same", "H": h, "J": j}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m)
        with session_scope() as s:
            job, _ = pdf.request_save(s, s.get(PdfDocument, doc.id))
            job_id = job.id
        drain()
    with session_scope() as s:
        assert s.get(Job, job_id).status == "conflict"
    assert sheet.appends == []


def test_save_not_configured_is_blocked_not_success(monkeypatch):
    from wg_core.config import settings

    with session_scope() as s:
        doc = PdfDocument(md5="f" * 32, original_name="x.pdf", size=1, doc_type="br", status="review",
                          fields={k: {"value": "x", "source": "manual"} for k in "ADEFGHIJ"}, extra={}, industry={})
        s.add(doc)
        s.flush()
        job, _ = pdf.request_save(s, doc)
        job_id = job.id
    monkeypatch.setenv("SHEET_ID", "")
    drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "SHEET_ID" in j.last_error


@needs_fixtures
def test_resave_after_stop_does_not_duplicate_or_flag_itself():
    """A save that stopped after Drive (e.g. Sheet down) and is saved again later uploads nothing twice."""
    data = open(BR[0], "rb").read()
    sheet = FakeSheet({})
    drive_calls = []
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m, fail_append=5)
        install_drive(m, calls=drive_calls)
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "doc.pdf", data)
            job, _ = pdf.request_save(s, doc)
            doc_id, job_id = doc.id, job.id
        drain()
        with session_scope() as s:  # give up on this job (as if it hit max attempts), then save again
            s.get(Job, job_id).status = "failed"
            s.get(PdfDocument, doc_id).status = "review"
        sheet2 = FakeSheet({})
        sheet2.install(m)
        with session_scope() as s:
            job2, created = pdf.request_save(s, s.get(PdfDocument, doc_id))
            assert created
        drain()
    with session_scope() as s:
        assert s.get(PdfDocument, doc_id).status == "saved"
    assert len(drive_calls) == 1 and len(sheet2.appends) == 1


@needs_fixtures
def test_k_is_xem_phoi_hyperlink_and_drive_file_is_reused_not_reuploaded():
    data = open(BR[0], "rb").read()
    import hashlib

    md5 = hashlib.md5(data).hexdigest()
    existing = {md5: {"id": "OLD1", "md5Checksum": md5, "webViewLink": "https://drive.google.com/file/d/OLD1/view"}}
    sheet, calls = FakeSheet({}), []
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m, calls=calls, existing=existing)  # e.g. uploaded before a crash, ID never saved
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "doc.pdf", data)
            pdf.request_save(s, doc)
            doc_id = doc.id
        drain()
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        assert d.status == "saved" and d.drive_file_id == "OLD1"
    assert calls == []  # found by md5 → no second upload
    row = d.sheet_row
    assert sheet.writes == [(f"K{row}", "Xem phôi → https://drive.google.com/file/d/OLD1/view")]


@pytest.mark.skipif(not CA, reason="California sample not present")
def test_scan_is_classified_and_read_by_ai_then_needs_owner_check(monkeypatch):
    import json as _json

    from tests.mocks import anthropic_json
    from wg_core.modules.pdf import ocr

    monkeypatch.setattr(ocr, "ocr_document", lambda data, **kw: [])  # a form the free OCR reader does not know → the AI

    ai_reply = {"doc_type": "ca", "evidence": "LLC-1, Secretary of State, State of California",
                "A": {"value": "EXAMPLE SUPPLY CO., LLC", "found": True}, "D": {"value": "", "found": False},
                "F": {"value": "100 EXAMPLE AVE.", "found": True}, "G": {"value": "LOS ANGELES", "found": True},
                "H": {"value": "California", "found": True}, "I": {"value": "90000", "found": True},
                "J": {"value": "2024 0000 0000", "found": True},
                "A_repeat": {"value": "Example Supply Co., LLC", "found": True}, "J_repeat": {"value": "202400000000", "found": True}}
    with respx.mock(assert_all_called=False) as m:
        route = m.post("https://api.anthropic.com/v1/messages").mock(return_value=anthropic_json(ai_reply))
        with session_scope() as s:
            doc, _ = pdf.ingest(s, "scan.pdf", open(CA[0], "rb").read())
            assert doc.status == "needs_ai" and doc.doc_type == "unknown"
            doc_id = doc.id
        drain()
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        assert d.doc_type == "ca" and d.status == "review" and "AI nhận diện" in d.detection_reason
        assert d.fields["A"] == {"value": "EXAMPLE SUPPLY CO., LLC", "source": "ai", "check": {"other": "Example Supply Co., LLC", "match": True}}
        assert d.fields["J"]["value"] == "202400000000" and d.fields["J"]["check"]["match"] is True  # same number on page 2
        assert d.fields["H"]["value"] == "CA"  # normalised, noted
        assert d.fields["E"]["value"] == "examplesup"
        # scanned → A/J read by AI → cannot be saved until the owner ticks "đã đối chiếu"
        assert any("đối chiếu" in r for r in pdf.save_check(d, confirm_missing=True, critical_checked=False))
        assert not pdf.save_check(d, confirm_missing=True, critical_checked=True)
    sent = _json.loads(route.calls[0].request.content)
    assert sent["model"] == "claude-opus-5-5"
    assert sent["messages"][0]["content"][0]["type"] == "document"
    assert sent["output_config"]["format"]["type"] == "json_schema" and sent["fallbacks"] == "default"


def test_scan_of_an_unknown_form_without_ai_key_says_what_to_do(monkeypatch):
    from wg_core.modules.pdf import ocr

    if not CA:
        pytest.skip("California sample not present")
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    other = [ocr.Page(0, [ocr.Box(10, 10, 90, 20, "INVOICE NO 12", 0.99)], 100, 100, words="INVOICENO12")]  # read, but no known form
    monkeypatch.setattr(ocr, "ocr_document", lambda data, **kw: other)
    with session_scope() as s:
        doc, _ = pdf.ingest(s, "scan.pdf", open(CA[0], "rb").read())
        assert doc.status == "needs_ai"
        doc_id = doc.id
    assert drain() == 1  # the free OCR read only; no AI call without a key
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        assert d.status == "needs_ai" and d.error.startswith("UNKNOWN_DOCUMENT") and "INVOICE" in d.error


@pytest.mark.skipif(not CA, reason="California sample not present")
def test_california_2013_scan_is_read_by_the_free_ocr_on_this_machine(monkeypatch):
    """The real RapidOCR run on the real scan (~15 s): no key, nothing sent out."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "")
    with session_scope() as s:
        doc, _ = pdf.ingest(s, "scan.pdf", open(CA[0], "rb").read())
        doc_id = doc.id
    drain()
    with session_scope() as s:
        d = s.get(PdfDocument, doc_id)
        assert d.doc_type == "ca" and d.status == "review" and d.detection_reason.startswith("OCR: mẫu LLC-1")
        f = {k: v["value"] for k, v in d.fields.items()}
        assert f["J"] == "201335710358" and f["H"] == "CA" and f["I"] == "90058" and f["G"] == "Vernon"
        assert f["F"] == "5051 Santa Fe Ave., Vernon, CA 90058" and d.fields["A"]["source"] == "ocr"
        assert f["A"].endswith("Co., LLC")
        # no phone on the form: a temporary number with the state's area code (owner, 2026-10-19)
        assert f["D"].startswith("(213) 555-01") and d.fields["D"]["phone_source"] == "placeholder"


def test_california_number_that_differs_on_page_2_blocks_saving_until_fixed_by_hand():
    from wg_core.modules.pdf.extract import fields_from_ai
    from wg_core.modules.pdf.fields import blocking, field, validate

    base = {"A": {"value": "EXAMPLE SUPPLY CO., LLC", "found": True}, "D": {"value": "", "found": False},
            "F": {"value": "100 EXAMPLE AVE.", "found": True}, "G": {"value": "LOS ANGELES", "found": True},
            "H": {"value": "CA", "found": True}, "I": {"value": "90000", "found": True},
            "J": {"value": "202400000008", "found": True}}
    f = fields_from_ai({**base, "J_repeat": {"value": "202400000003", "found": True},
                        "A_repeat": {"value": "EXAMPLE SUPPLY CO LLC", "found": True}}, "ca")
    issues = validate(f, "ca")
    assert issues["J"]["level"] == "error" and "202400000003" in issues["J"]["message"]
    assert "A" not in issues  # punctuation-only difference in the name is a match
    f["J"] = field("202400000003", "manual")  # owner checked the PDF and typed the number
    assert "J" not in blocking(validate(f, "ca"))
    # not printed again → only a warning to check by eye
    f2 = fields_from_ai({**base, "J_repeat": {"value": "", "found": False}, "A_repeat": {"value": "", "found": False}}, "ca")
    assert validate(f2, "ca")["J"]["level"] == "warn"
    # a different name on page 2 is flagged (warning)
    f3 = fields_from_ai({**base, "J_repeat": {"value": "202400000008", "found": True},
                         "A_repeat": {"value": "OTHER NAME LLC", "found": True}}, "ca")
    assert validate(f3, "ca")["A"]["level"] == "warn" and "J" not in validate(f3, "ca")


def test_new_row_goes_into_the_first_empty_row_under_the_owners_block_never_over_data():
    """Owner, 2026-10-20: rows 3–4 filled, 5 empty, 9 filled further down → the next row is 5 (not after 9, which the
    Sheets "append" call would pick); a row that got data meanwhile is never overwritten."""
    from wg_core.integrations.errors import Transient
    from wg_core.integrations.google import Sheets

    sheet = FakeSheet({3: {"A": "One"}, 4: {"A": "Two"}, 9: {"I": "91304", "J": "201099900048", "K": "Xem phôi"}})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        assert Sheets().append_row(["New Co", "", "", "", "newco", "", "", "", "", "201099900001", ""]) == 5
        assert sheet.rows[5]["A"] == "New Co" and sheet.rows[9]["J"] == "201099900048"  # the stray row untouched
        assert Sheets().append_row(["Next Co"] + [""] * 10) == 6
    busy = FakeSheet({3: {"A": "One"}, 4: {"A": "Typed meanwhile"}})
    with respx.mock(assert_all_called=False) as m:
        busy.install(m)
        # the empty-row scan said 4, but someone typed there before the write: re-read → refused, nothing overwritten
        orig = Sheets.next_empty_row
        Sheets.next_empty_row = lambda self, c: 4
        try:
            with pytest.raises(Transient):
                Sheets().append_row(["X"] + [""] * 10)
        finally:
            Sheets.next_empty_row = orig
        assert busy.rows[4] == {"A": "Typed meanwhile"} and not busy.appends
