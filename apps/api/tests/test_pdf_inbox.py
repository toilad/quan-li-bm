"""PDF inbox folder (owner, 2026-10-20): PDFs dropped in the Desktop folder "Ảnh Phôi" are read like an upload and deleted for good
as soon as the app holds its own copy (md5 checked). Temp folder, fake Sheet / Drive."""
import hashlib

import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, install_drive
from tests.test_pdf import BR, needs_fixtures

from wg_core.db import session_scope
from wg_core.models import PdfDocument
from wg_core.modules.pdf import inbox
from wg_core.modules.pdf.service import storage_path


def pdf(tag: str) -> bytes:
    return f"%PDF-1.4 {tag}\n%%EOF\n".encode()


def test_taken_into_the_app_then_deleted_at_once_review_too(tmp_path, monkeypatch):
    """Owner: keep the disk small — a PDF is deleted from the folder as soon as the app holds its own copy, even one
    still to review (the app reads, reviews and uploads to Drive from that copy)."""
    monkeypatch.setenv("PDF_INBOX_DIR", str(tmp_path))
    monkeypatch.setattr(inbox, "_sizes", {})
    files = {"a.pdf": pdf("a"), "a - Copy.PDF": pdf("a"), "review.pdf": pdf("review"),
             "half.pdf": b"%PDF-1.4 still copying", "notes.pdf": b"not a pdf"}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "keep.txt").write_text("not touched")
    read = []

    def fake_ingest(s, name, data):
        doc = PdfDocument(md5=hashlib.md5(data).hexdigest(), original_name=name, size=len(data), fields={}, extra={},
                          industry={}, status="review")
        if name != "review.pdf":
            storage_path(doc.md5).write_bytes(data)  # review.pdf: the app copy is missing → the file must stay
        s.add(doc)
        s.flush()
        read.append(name)
        return doc, True

    monkeypatch.setattr(inbox, "ingest", fake_ingest)
    with session_scope() as s:
        assert inbox.scan(s, log=lambda m: None)["read"] == 0  # first look: sizes only (a copy may still be running)
        r = inbox.scan(s, log=lambda m: None)
        st = inbox.status(s)
    assert r["read"] == 2 and r["deleted"] == 2 and sorted(read) == ["a - Copy.PDF", "review.pdf"]  # same bytes read once
    assert sorted(f.name for f in tmp_path.iterdir()) == ["half.pdf", "keep.txt", "notes.pdf", "review.pdf"]
    assert st["files"] == 3 and st["bad"] == 1 and st["pending"] == 2
    storage_path(hashlib.md5(pdf("review")).hexdigest()).write_bytes(pdf("review"))
    with session_scope() as s:
        assert inbox.scan(s, log=lambda m: None)["deleted"] == 1  # app copy now there → deleted, nothing read twice
    assert len(read) == 2 and not (tmp_path / "review.pdf").exists()


def test_app_copy_must_match_before_the_folder_file_goes(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_INBOX_DIR", str(tmp_path))
    data = pdf("x")
    (tmp_path / "x.pdf").write_bytes(data)
    md5 = hashlib.md5(data).hexdigest()
    storage_path(md5).write_bytes(b"%PDF damaged copy")
    with session_scope() as s:
        s.add(PdfDocument(md5=md5, original_name="x.pdf", size=len(data), fields={}, extra={}, industry={}, status="review"))
    with session_scope() as s:
        inbox.scan(s, log=lambda m: None)
        assert inbox.scan(s, log=lambda m: None)["deleted"] == 0
    assert (tmp_path / "x.pdf").exists()
    monkeypatch.setenv("PDF_INBOX_DIR", "off")
    assert inbox.inbox_dir() is None


@needs_fixtures
def test_real_flow_folder_to_sheet_then_file_deleted(tmp_path, monkeypatch):
    monkeypatch.setenv("AUTO_SAVE_TO_SHEET", "true")
    monkeypatch.setenv("MANUAL_REVIEW_MODE", "false")
    monkeypatch.setenv("PDF_INBOX_DIR", str(tmp_path))
    (tmp_path / "phoi.pdf").write_bytes(open(BR[0], "rb").read())
    sheet = FakeSheet({})
    with respx.mock(assert_all_called=False) as m:
        sheet.install(m)
        install_drive(m)
        with session_scope() as s:
            inbox.scan(s, log=lambda m: None)
            assert inbox.scan(s, log=lambda m: None)["read"] == 1
        assert not (tmp_path / "phoi.pdf").exists()  # taken in → deleted at once; the app copy goes on to the Sheet
        drain()
    assert len(sheet.appends) == 1
