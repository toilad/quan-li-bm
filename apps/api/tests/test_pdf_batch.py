"""Folder → one results file, one row appended per PDF (made-up values, no real PDF, no OCR run)."""
import csv

from wg_core.modules.pdf import batch, ocr


def test_one_row_per_pdf_appended_duplicates_skipped_review_keeps_candidates(tmp_path, monkeypatch):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "a.pdf").write_bytes(b"%PDF a")
    (folder / "a - Copy.pdf").write_bytes(b"%PDF a")  # same content, another name
    (folder / "b.pdf").write_bytes(b"%PDF b")
    rows = {b"%PDF a": {"entity_name": "Sample Holdings, LLC", "business_full_address": "1 Sample St, Los Angeles, CA 90001",
                        "business_street": "1 Sample St", "business_city": "Los Angeles", "business_state": "CA",
                        "business_zip": "90001", "state_file_number": "201099900001", "document_type": "LLC-5 REV 04/2007",
                        "status": "OK", "confidence": 97, "reason": "Địa chỉ lấy từ ô mục 7"},
            b"%PDF b": {"entity_name": "Sample Holdings Ill, LLC", "status": "REVIEW_REQUIRED", "reason": "III/Ill"}}
    monkeypatch.setattr(batch, "_text_layer_row", lambda data: None)
    monkeypatch.setattr(batch, "_scan_row", lambda data, force=False: rows[data])
    out = tmp_path / "extracted_results.csv"
    s = batch.run(folder, out)
    assert s["files"] == 2 and s["duplicates"] == 1
    got = list(csv.DictReader(out.open(encoding="utf-8-sig")))
    assert [r["source_file"] for r in got] == ["a - Copy.pdf", "b.pdf"]
    assert got[0]["business_full_address"] == "1 Sample St, Los Angeles, CA 90001" and got[0]["business_city"] == "Los Angeles"
    assert got[1]["entity_name"] == "Sample Holdings Ill, LLC" and got[1]["status"] == "REVIEW_REQUIRED"  # candidate kept
    assert got[0]["check"] == "OK" and got[1]["check"].startswith("CẦN DUYỆT")
    batch.run(folder, out)  # a second run appends below, the header is not repeated
    assert len(list(csv.DictReader(out.open(encoding="utf-8-sig")))) == 4


def test_ocr_cache_is_small_json_capped_and_clearable(tmp_path, monkeypatch):
    monkeypatch.setenv("OCR_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setenv("OCR_CACHE_LIMIT_MB", "10")
    d = tmp_path / "cache" / "ab"
    d.mkdir(parents=True)
    (d / "ab-p1-original-x.json").write_text("{}")
    (d / "ab-p1-threshold-x.json").write_text("{}")  # an old whole-page variant: no longer read
    big = d / "ab-p2-original-x.json"
    big.write_bytes(b" " * 11_000_000)
    import os, time  # noqa: E401

    os.utime(big, (time.time() - 100, time.time() - 100))  # the oldest page goes first
    assert ocr.prune_cache() == 2
    assert [f.name for f in d.iterdir()] == ["ab-p1-original-x.json"]
    assert ocr.cache_info()["mode"] == "minimal" and ocr.clear_cache() == 1 and ocr.cache_info()["files"] == 0


def test_files_and_folders_picked_together_unknown_gets_no_guess(tmp_path, monkeypatch):
    folder = tmp_path / "in"
    folder.mkdir()
    (folder / "x.pdf").write_bytes(b"%PDF x")
    (folder / "notes.txt").write_text("not a pdf")
    single = tmp_path / "y.PDF"
    single.write_bytes(b"%PDF y")
    rows = {b"%PDF x": {"status": "UNKNOWN_DOCUMENT", "entity_name": "guess", "reason": "Không khớp mẫu"},
            b"%PDF y": {"status": "NO_BUSINESS_ADDRESS_ON_FORM", "entity_name": "Sample LLC", "state_file_number": "201099900001"}}
    monkeypatch.setattr(batch, "_text_layer_row", lambda data: None)
    monkeypatch.setattr(batch, "_scan_row", lambda data, force=False: rows[data])
    out = tmp_path / "r.csv"
    s = batch.run([folder, single], out)
    got = {r["source_file"]: r for r in csv.DictReader(out.open(encoding="utf-8-sig"))}
    assert s["files"] == 2 and set(got) == {"x.pdf", "y.PDF"}
    assert got["x.pdf"]["entity_name"] == "" and got["x.pdf"]["check"].startswith("KHÔNG ĐỌC")  # nothing guessed
    assert got["y.PDF"]["business_full_address"] == "" and got["y.PDF"]["check"].startswith("OK")
