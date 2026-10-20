"""The two daily jobs: search keywords into the pool, then download initial filings.

Both are strictly sequential and stop as soon as their goal is met.
"""
from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Callable

from . import rules
from .bizfile import Bizfile, BizfileError
from .store import DONE, ERROR, FAILED, NOT_RUN, OK, RUNNING, SKIPPED, Store

DAILY_DOWNLOAD_GOAL = 50
TARGET_BUFFER = 10
POOL_GOAL = DAILY_DOWNLOAD_GOAL + TARGET_BUFFER
BATCH_SIZE = 5
SEARCH_CAP = 500
SLICE_YEARS = range(2016, 1993, -1)  # LLCs exist in California since 1994

Progress = Callable[[dict], None]


# ---- keyword choice -------------------------------------------------------
def random_batch(store: Store, n: int = BATCH_SIZE, rng: random.Random | None = None) -> list[str]:
    """Distinct keywords, never-run first. Only when none is left: the least recently run."""
    rng = rng or random.Random()
    rows = store.keyword_rows()
    fresh = [r["keyword"] for r in rows if r["status"] == NOT_RUN]
    if fresh:
        return rng.sample(fresh, min(n, len(fresh)))
    failed = [r["keyword"] for r in rows if r["status"] == FAILED]
    if failed:
        return rng.sample(failed, min(n, len(failed)))
    oldest = sorted(rows, key=lambda r: r["last_run"] or "")
    return [r["keyword"] for r in oldest[:n]]


# ---- search ---------------------------------------------------------------
def _take(store: Store, rows: list[dict], keyword: str, max_len: int, active_only: bool) -> tuple[int, int]:
    valid = new = 0
    for row in rows:
        t = rules.parse_row(row)
        if t and rules.reject_reason(t, max_name_len=max_len, active_only=active_only) is None:
            valid += 1
            new += store.add_target(t, keyword)
    return valid, new


def run_search(bz: Bizfile, store: Store, keywords: list[str], *, pool_goal: int = POOL_GOAL,
               max_len: int = rules.DEFAULT_MAX_NAME_LEN, active_only: bool = True,
               progress: Progress = lambda s: None, should_stop: Callable[[], bool] = lambda: False) -> list[dict]:
    summary = []
    for i, kw in enumerate(keywords[:BATCH_SIZE], 1):
        if store.pending_count() >= pool_goal or should_stop():
            break
        store.set_keyword(kw, RUNNING)
        progress({"phase": "search", "index": i, "total": len(keywords), "keyword": kw,
                  "pool": store.pending_count(), "pool_goal": pool_goal})
        raw = valid = new = 0
        try:
            rows = bz.search(kw)
            raw = len(rows)
            v, n = _take(store, rows, kw, max_len, active_only)
            valid, new = valid + v, new + n
            # Date slices only when the plain search hit the 500 cap and the pool is still short.
            if raw >= SEARCH_CAP:
                for year in SLICE_YEARS:
                    if store.pending_count() >= pool_goal or should_stop():
                        break
                    progress({"phase": "search", "index": i, "total": len(keywords), "keyword": f"{kw} ({year})",
                              "pool": store.pending_count(), "pool_goal": pool_goal})
                    rows = bz.search(kw, date_from=f"01/01/{year}", date_to=f"12/31/{year}")
                    raw += len(rows)
                    v, n = _take(store, rows, kw, max_len, active_only)
                    valid, new = valid + v, new + n
            store.set_keyword(kw, DONE, raw_count=raw, valid_count=valid, new_count=new, error=None)
            summary.append({"keyword": kw, "status": DONE, "raw": raw, "valid": valid, "new": new})
        except Exception as e:  # one keyword failing does not stop the batch
            if should_stop():  # stopped by the owner: the keyword stays not run
                store.set_keyword(kw, NOT_RUN, error=None)
                break
            store.set_keyword(kw, FAILED, raw_count=raw, valid_count=valid, new_count=new, error=str(e)[:300])
            summary.append({"keyword": kw, "status": FAILED, "raw": raw, "valid": valid, "new": new, "error": str(e)})
        progress({"phase": "search", "index": i, "total": len(keywords), "keyword": kw,
                  "pool": store.pending_count(), "pool_goal": pool_goal, "done": summary[-1]})
    return summary


# ---- download -------------------------------------------------------------
@dataclass
class Result:
    status: str              # OK | SKIPPED | ERROR
    filename: str | None
    note: str


def download_one(bz: Bizfile, store: Store, t, out_dir: Path) -> Result:
    """t: a targets row. Never substitutes another filing, never overwrites a file."""
    number, name = t["entity_number"], t["entity_name"]
    prev = store.download_of(number)
    if prev and prev["download_status"] == OK:
        return Result(SKIPPED, prev["local_filename"], "đã tải trước đó")

    tgt = rules.Target(name, number, t["date"], t["status"], t["entity_type"], t["record_id"], t["record_num"])
    if rules.converted_suspect(tgt):
        return Result(SKIPPED, None, "converted entity: initial filing is not an original LLC-1/LLC-5")
    pick = rules.pick_initial_filing(bz.history(t["record_num"]), number)
    if pick.filing is None:
        return Result(SKIPPED, None, pick.skip_reason)
    form = rules.expected_form(t["entity_type"])

    base = rules.safe_filename(name)
    alt = rules.safe_filename(name, number)
    if (out_dir / alt).exists():
        return Result(SKIPPED, alt, "đã có file cùng Entity Number")
    if (out_dir / base).exists() and store.entity_for_filename(base) == number:
        return Result(SKIPPED, base, "đã có file cùng Entity Number")

    data = bz.download(pick.filing["DOWNLOAD_LINK"])
    out_dir.mkdir(parents=True, exist_ok=True)
    if (out_dir / base).exists():
        if (out_dir / base).read_bytes() == data:
            return Result(SKIPPED, base, "đã có file, cùng tài liệu")
        target = out_dir / alt   # another company with the same name
    else:
        target = out_dir / base
    with open(target, "xb") as fh:  # "x": fail rather than overwrite
        fh.write(data)
    return Result(OK, target.name, f"{form}, initial {pick.filing['AMENDMENT_DATE']}, {len(data):,} bytes")


def run_download(bz: Bizfile, store: Store, out_dir: Path, *, goal: int = DAILY_DOWNLOAD_GOAL,
                 progress: Progress = lambda s: None, should_stop: Callable[[], bool] = lambda: False) -> dict:
    successful = store.ok_today()
    log = []
    for t in store.pending_targets():
        if successful >= goal or should_stop():
            break
        progress({"phase": "download", "ok": successful, "goal": goal, "current": t["entity_name"]})
        try:
            res = download_one(bz, store, t, out_dir)
        except BizfileError as e:
            if should_stop():  # stopped by the owner: leave this target pending
                break
            res = Result(ERROR, None, str(e)[:300])
        except Exception as e:  # one target failing does not stop the batch
            res = Result(ERROR, None, str(e)[:300])
        store.record_download(t["entity_number"], t["entity_name"], t["keyword_source"],
                              res.status, res.filename, res.note)
        successful += res.status == OK
        log.append({"entity_number": t["entity_number"], "name": t["entity_name"], **res.__dict__})
        progress({"phase": "download", "ok": successful, "goal": goal, "current": t["entity_name"], "last": log[-1]})
    return {"ok_today": successful, "goal": goal, "log": log, "day": date.today().isoformat()}
