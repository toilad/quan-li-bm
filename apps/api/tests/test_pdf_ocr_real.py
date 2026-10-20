"""REAL OCR on the owner's real scans (opt-in: RUN_REAL_OCR=1; ~4 min). The PDFs and their reference values stay out of
Git (test-fixtures/pdf/ca, test-fixtures/expected.local.json → "ca_ocr"). Unlike tests/test_pdf_ocr.py (mocked boxes),
this proves what the engine actually reads from each file.

Each value must be either exactly the reference, or flagged for the owner (a suspicion shown next to the cell) — a wrong
value without a flag fails. An agent / Return-to address must never land in F–I."""
import json
import os
import re
from pathlib import Path

import pytest

from wg_core.modules.pdf.ocr import extract_ca_scan, ocr_document, read_scan

ROOT = Path(__file__).resolve().parents[3] / "test-fixtures"
FILES = ROOT / "pdf" / "ca"
EXPECTED = json.loads((ROOT / "expected.local.json").read_text(encoding="utf-8")).get("ca_ocr", {}) \
    if (ROOT / "expected.local.json").exists() else {}

pytestmark = pytest.mark.skipif(os.environ.get("RUN_REAL_OCR") != "1" or not EXPECTED or not FILES.exists(),
                                reason="real OCR is opt-in (RUN_REAL_OCR=1) and needs test-fixtures/pdf/ca + expected.local.json")
_cache: dict = {}


def read(name: str):
    if name not in _cache:
        data = (FILES / name).read_bytes()
        _cache[name] = extract_ca_scan(ocr_document(data), data)
    return _cache[name]


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", (s or "").strip()).lower()


def flagged(cell: dict, hint: str = "") -> bool:
    return any(hint.lower() in (s["message"] + s.get("suggestion", "")).lower() for s in cell.get("suspects", [])) or bool(cell.get("warning"))


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_real_scan(name):
    want = EXPECTED[name]
    got = read(name)
    assert got, f"{name}: form not recognised"
    f, extra = got
    # A: exact, or flagged; a handwritten name (reference None) must be left empty with a note
    if want["A"] is None:
        assert f["A"]["value"] == "" and f["A"].get("note")
    elif norm(f["A"]["value"]) != norm(want["A"]):
        assert flagged(f["A"], want.get("flag_A", "")), (name, f["A"])
    # J: exact (kept as text, 12 digits)
    assert f["J"]["value"] == want["J"] and isinstance(f["J"]["value"], str)
    # address: the company's own one in F–I, a suggestion otherwise (never F)
    role, street, city, state, zipc = want["addr"]
    if role in ("principal", "mailing"):
        have_street = f["F"]["value"].rsplit(", " + f["G"]["value"], 1)[0]
        assert (f["G"]["value"], f["H"]["value"], f["I"]["value"]) == (city, state, zipc), (name, f["F"])
        # F = the FULL address: the street read, then exactly G, H I (owner, 2026-10-20)
        assert f["F"]["value"] == f'{f["F"]["street"]}, {city}, {state} {zipc}', (name, f["F"]["value"])
        assert norm(have_street) == norm(street) or flagged(f["F"], want.get("flag_F", "")), (name, have_street)
    else:
        assert f["F"]["value"] == f["G"]["value"] == f["I"]["value"] == "", (name, "agent/return-to address put in F–I")
        c = next(c for c in extra["address_candidates"] if c["role"] == role)
        assert (c["city"], c["state"], c["zip"]) == (city, state, zipc)
        hint = want.get("flag_addr", "")
        assert norm(c["street"]) == norm(street) or any(hint.lower() in s["message"].lower() for s in c.get("suspects", [])), c
    assert f["D"]["value"] == ""  # no phone box on these forms; nothing taken from other pages
    if "formation" in want:
        assert norm(extra.get("formation_state")) == norm(want["formation"][0]) and extra.get("formation_date") == want["formation"][1]
    if "filed" in want:
        assert extra["filed_date"] == want["filed"]
    if want.get("no_candidates"):
        assert extra["address_candidates"] == []  # item 8 blank: nothing invented
    if "agent" in want:
        assert norm(extra["agent_name"]) == norm(want["agent"])
    if "version" in want:
        assert extra["version"] == want["version"] and extra["version_verified"]


@pytest.mark.parametrize("name", sorted(n for n, w in EXPECTED.items() if "status" in w))
def test_real_scan_status_and_rejected_addresses(name):
    """The whole reading (read_scan, image variants included): status per form, and the addresses turned down."""
    want = EXPECTED[name]
    r = read_scan((FILES / name).read_bytes())
    assert r["status"] == want["status"], (name, r["reason"])
    assert not {c["role"] for c in r["selected_candidates"]} & {"agent", "return_to", "general_partner", "organizer"}
    if "rejected" in want:
        assert sorted(c["role"] for c in r["rejected_candidates"]) == sorted(want["rejected"])
