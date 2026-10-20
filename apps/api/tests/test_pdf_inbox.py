"""PDF inbox folder (owner, 2026-10-20): PDFs dropped in Desktop\\Ảnh Phôi are read like an upload; a file is deleted
for good only once its row is on the Sheet (Drive md5 checked) or it is a duplicate. Temp folder, fake Sheet / Drive."""
import hashlib

import respx
from tests.conftest import drain
from tests.mocks import FakeSheet, install_drive
from tests.test_pdf import BR, needs_fixtures

from wg_core.db import session_scope
from wg_core.models import PdfDocument
from wg_core.modules.pdf import inbox


def pdf(tag: str) -> bytes:
    return f"%PDF-1.4 {tag}\n%%EOF\n".encode()


def test_new_files_read_finished_ones_deleted_the_rest_kept(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_INBOX_DIR", str(tmp_path))
    monkeypatch.setattr(inbox, "_sizes", {})
    files = {"saved.pdf": pdf("saved"), "saved - Copy.PDF": pdf("saved"), "dup.pdf": pdf("dup"), "review.pdf": pdf("review"),
             "half.pdf": b"%PDF-1.4 still copying", "notes.pdf": b"not a pdf"}
    for name, data in files.items():
        (tmp_path / name).write_bytes(data)
    (tmp_path / "keep.txt").write_text("not touched")
    read = []

    def fake_ingest(s, name, data):
        doc = PdfDocument(md5=hashlib.md5(data).hexdigest(), original_name=name, size=len(data), fields={}, extra={},
                          industry={}, status="review")
        s.add(doc)
        s.flush()
        read.append(name)
        return doc, True

    monkeypatch.setattr(inbox, "ingest", fake_ingest)
    with session_scope() as s:
        assert inbox.scan(s, log=lambda m: None)["read"] == 0  # first look: sizes only (a copy may still be running)
        r = inbox.scan(s, log=lambda m: None)
    assert r["read"] == 3 and r["deleted"] == 0 and sorted(read) == ["dup.pdf", "review.pdf", "saved - Copy.PDF"]
    with session_scope() as s:
        for d in s.query(PdfDocument).filter(PdfDocument.original_name.in_(read)):
            if d.original_name.startswith("saved"):
                d.status, d.drive_file_id, d.sheet_row = "saved", "drive-1", 730
            elif d.original_name == "dup.pdf":
                d.status, d.extra = "failed", {"duplicate": True}
    with session_scope() as s:
        r = inbox.scan(s, log=lambda m: None)
        st = inbox.status(s)
    left = sorted(f.name for f in tmp_path.iterdir())
    assert r["deleted"] == 3 and left == ["half.pdf", "keep.txt", "notes.pdf", "review.pdf"]  # both copies + the duplicate
    assert st["files"] == 3 and st["review"] == 1 and st["pending"] == 2


def test_failed_save_that_is_not_a_duplicate_keeps_the_file(tmp_path, monkeypatch):
    monkeypatch.setenv("PDF_INBOX_DIR", str(tmp_path))
    data = pdf("drive md5 mismatch")
    (tmp_path / "x.pdf").write_bytes(data)
    with session_scope() as s:
        s.add(PdfDocument(md5=hashlib.md5(data).hexdigest(), original_name="x.pdf", size=len(data), fields={}, extra={},
                          industry={}, status="failed", error="md5 trên Drive khác file gốc"))
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
        assert (tmp_path / "phoi.pdf").exists()  # not deleted before the Sheet write
        drain()
        with session_scope() as s:
            assert inbox.scan(s, log=lambda m: None)["deleted"] == 1
    assert not (tmp_path / "phoi.pdf").exists() and len(sheet.appends) == 1
