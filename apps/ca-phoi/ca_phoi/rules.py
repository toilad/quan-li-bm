"""Pure rules: parse a search row, filter targets, pick the initial filing, name the file.

No browser and no database here, so every rule can be tested offline.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

# Initial Filing Date window (owner, 2026-10-21): 2007–2013 are the years whose forms the PDF reader
# handles (LLC-1/LLC-5 REV 03/2005, 04/2007 …); 2014–2016 filings (REV 01/2014+) all landed in review.
DATE_FROM = "2007-01-01"
DATE_LIMIT = "2014-01-01"
DEFAULT_MAX_NAME_LEN = 30

DOMESTIC_LLC = "Limited Liability Company - CA"
FOREIGN_LLC = "Limited Liability Company - Out of State"

_TITLE_RE = re.compile(r"^(?P<name>.*\S)\s*\((?P<num>[0-9A-Z]+)\)\s*$")
_LLC_END_RE = re.compile(r"(?:\s|,\s*)LLC$")  # "... LLC" or "..., LLC" (also ",LLC")
_ILLEGAL_RE = re.compile(r'[\\/:*?"<>|]')


@dataclass(frozen=True)
class Target:
    entity_name: str
    entity_number: str
    date: str          # ISO yyyy-mm-dd (Initial Filing Date)
    status: str
    entity_type: str
    record_id: int
    record_num: str    # key for /api/History/business/{record_num}


def parse_row(row: dict) -> Target | None:
    m = _TITLE_RE.match((row.get("TITLE") or [""])[0])
    if not m:
        return None
    try:
        mo, d, y = row["FILING_DATE"].split("/")
        iso = f"{int(y):04d}-{int(mo):02d}-{int(d):02d}"
    except (KeyError, ValueError):
        return None
    return Target(m["name"].strip(), m["num"], iso, row.get("STATUS", ""),
                  row.get("ENTITY_TYPE", ""), int(row.get("ID", 0)), row.get("RECORD_NUM", ""))


def is_llc(entity_type: str) -> bool:
    return entity_type in (DOMESTIC_LLC, FOREIGN_LLC)


def converted_suspect(t: Target) -> bool:
    """A 12-digit CA number starts with the year it was filed. When that year differs
    from the Initial Filing Date, the record was converted from an older entity
    (e.g. 201622510332: LLC-1A conversion in 2016 of a 2010 corporation), so its
    initial filing is not an original LLC-1 / LLC-5 and its date is not the LLC's."""
    num = t.entity_number
    if not (len(num) == 12 and num.isdigit()):
        return False
    num_year, date_year = int(num[:4]), int(t.date[:4])
    if num_year == date_year:
        return False
    return not (num_year == date_year + 1 and t.date[5:7] == "12")  # filed late Dec, numbered in Jan


def reject_reason(t: Target, *, max_name_len: int = DEFAULT_MAX_NAME_LEN,
                  active_only: bool = True) -> str | None:
    """None when the target passes the owner's filter, otherwise why it fails."""
    if not is_llc(t.entity_type):
        return "not LLC"
    if converted_suspect(t):
        return "converted entity (number year != filing year)"
    if active_only and t.status != "Active":
        return "not Active"
    if not DATE_FROM <= t.date < DATE_LIMIT:
        return "filed outside 2007–2013"
    if len(t.entity_name) > max_name_len:
        return "name too long"
    if not _LLC_END_RE.search(t.entity_name.upper()):
        return "name does not end in LLC"
    return None


def expected_form(entity_type: str) -> str:
    if entity_type == DOMESTIC_LLC:
        return "LLC-1 Articles of Organization"
    if entity_type == FOREIGN_LLC:
        return "LLC-5 Application to Register"
    return "?"


@dataclass(frozen=True)
class Pick:
    filing: dict | None
    skip_reason: str | None


def pick_initial_filing(filings: list[dict], entity_number: str) -> Pick:
    """Exactly one "Initial Filing" with a PDF, numbered as the entity. Never a substitute."""
    initial = [f for f in filings if (f.get("AMENDMENT_TYPE") or "").strip() == "Initial Filing"]
    if any("conversion" in (f.get("AMENDMENT_TYPE") or "").lower() for f in filings):
        return Pick(None, "history has a Conversion: not an original LLC-1/LLC-5")
    if not initial:
        return Pick(None, "no Initial Filing in history")
    if len(initial) > 1:
        return Pick(None, f"{len(initial)} Initial Filings, ambiguous")
    f = initial[0]
    if (f.get("AMENDMENT_NUM") or "").strip() != entity_number:
        return Pick(None, f"Initial Filing number {f.get('AMENDMENT_NUM')} != {entity_number}")
    if not f.get("DOWNLOAD_LINK"):
        return Pick(None, "Initial Filing has no PDF")
    return Pick(f, None)


def safe_filename(entity_name: str, entity_number: str | None = None) -> str:
    """'SNC MANAGEMENT & HOLDINGS, LLC' -> 'SNC MANAGEMENT & HOLDINGS LLC.pdf'."""
    name = re.sub(r"\s*,\s*(LLC\.?)$", r" \1", entity_name.strip(), flags=re.I)
    name = _ILLEGAL_RE.sub(" ", name)
    name = re.sub(r"\s+", " ", name).strip().rstrip(". ")
    if entity_number:
        name = f"{name} - {entity_number}"
    return f"{name}.pdf"
