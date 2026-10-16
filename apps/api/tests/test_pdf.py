import glob

import pytest
import respx
from tests.conftest import FIXTURES, drain
from tests.mocks import FakeSheet, install_drive

from wg_core.db import session_scope
from wg_core.models import Job, PdfDocument, SheetWrite
from wg_core.modules.pdf import service as pdf
from wg_core.modules.pdf.extract import detect, extract_br, read_pdf
from wg_core.modules.pdf.fields import cnpj_valid, validate

BR = sorted(glob.glob(str(FIXTURES / "*.pdf")))
CA = sorted(glob.glob(str(FIXTURES / "*.pdf")))
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
        assert len(f["I"]["value"]) == 10 and f["I"]["value"][2] == "."  # CEP kept as printed, text
        assert " - " in f["F"]["value"] and "*" not in f["F"]["value"]
        assert extra["situacao_cadastral"] == "ATIVA"
        assert not {k for k, v in validate(f, "br").items() if v["level"] == "error"}


@needs_fixtures
def test_brazil_known_values_one_sample():
    p = BR[0]
    f, extra = extract_br(read_pdf(open(p, "rb").read()))
    assert f["A"]["value"] == "<redacted sample name>"
    assert f["J"]["value"] == "11.222.333/0001-81"
    assert f["F"]["value"] == "<redacted sample address>"
    assert (f["G"]["value"], f["H"]["value"], f["I"]["value"]) == ("<redacted>", "<redacted>", "<redacted>")
    assert f["E"]["value"] == "<redacted>"
    assert extra["cnae_principal"].startswith("95.11-8-00")


@pytest.mark.skipif(not CA, reason="California sample not present")
def test_california_scan_is_not_guessed():
    t = read_pdf(open(CA[0], "rb").read())
    d = detect(t)
    assert d.doc_type == "unknown" and "scan" in d.reason  # no text layer → owner picks type → AI reads


def test_cnpj_checksum():
    assert cnpj_valid("11.222.333/0001-81")
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
            assert s.query(SheetWrite).count() == 1
    assert len(drive_calls) == 1  # never uploaded twice
    row = sheet.appends[0]
    assert row[1] == "" and row[2] == ""  # B, C empty
    assert row[10] == "https://drive.google.com/file/d/DRIVE123/view"  # K = link to the original PDF
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
    monkeypatch.setattr(settings(), "sheet_id", "")
    drain()
    with session_scope() as s:
        j = s.get(Job, job_id)
        assert j.status == "blocked" and "SHEET_ID" in j.last_error
