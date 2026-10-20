"""Live regression on Bizfile (needs the verified Edge window). Uses a throwaway DB.

  .venv\\Scripts\\python.exe -m tests.regression_live "<out folder>" "<test db path>"
"""
import sqlite3
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

from ca_phoi import rules
from ca_phoi.bizfile import Bizfile
from ca_phoi.jobs import download_one
from ca_phoi.store import Store


def as_row(t: rules.Target, keyword="regression") -> dict:
    return {**t.__dict__, "keyword_source": keyword}


def show(label, res):
    print(f"  {label}: {res.status} | {res.filename} | {res.note}", flush=True)
    return res


def main():
    out, db = Path(sys.argv[1]), Path(sys.argv[2])
    store = Store(db)
    with sync_playwright() as pw:
        bz = Bizfile(pw)
        rows = [rules.parse_row(r) for r in bz.search("Holdings")]
        valid = [t for t in rows if t and rules.reject_reason(t) is None]
        dom = [t for t in valid if t.entity_type == rules.DOMESTIC_LLC]
        foreign = [t for t in valid if t.entity_type == rules.FOREIGN_LLC]
        print(f"search Holdings: {len(rows)} rows, {len(valid)} valid ({len(dom)} domestic, {len(foreign)} foreign)")
        snc = next(t for t in rows if t and t.entity_number == "200412110197") if any(
            t and t.entity_number == "200412110197" for t in rows) else None

        conv = [t for t in rows if t and rules.is_llc(t.entity_type) and rules.converted_suspect(t)]
        print("converted (filtered out):", [(t.entity_name, t.entity_number, t.date) for t in conv][:5])
        print("\n[1] Domestic LLC")
        d = next(t for t in dom if t.entity_number != "200412110197")
        print(f"  target: {d.entity_name} ({d.entity_number}) {d.date} {d.status}")
        r = show("download", download_one(bz, store, as_row(d), out))
        store.record_download(d.entity_number, d.entity_name, "regression", r.status, r.filename, r.note)

        print("\n[2] Foreign LLC")
        if not foreign:
            for kw in ("Partners", "Capital"):
                more = [rules.parse_row(x) for x in bz.search(kw)]
                foreign = [t for t in more if t and rules.reject_reason(t) is None
                           and t.entity_type == rules.FOREIGN_LLC]
                if foreign:
                    break
        f = foreign[0]
        print(f"  target: {f.entity_name} ({f.entity_number}) {f.date} {f.status} [{f.entity_type}]")
        r = show("download", download_one(bz, store, as_row(f), out))
        store.record_download(f.entity_number, f.entity_name, "regression", r.status, r.filename, r.note)

        print("\n[3] Edge cases")
        print("  3a. same entity again (file in folder + history):")
        show("domestic again", download_one(bz, store, as_row(d), out))
        print("  3b. SNC again: file exists from the prototype, history DB does not know it:")
        if snc is None:
            snc = next(rules.parse_row(x) for x in bz.search("SNC MANAGEMENT & HOLDINGS")
                       if x["TITLE"][0].endswith("(200412110197)"))
        before = (out / "SNC MANAGEMENT & HOLDINGS LLC.pdf").stat().st_mtime
        show("SNC", download_one(bz, store, as_row(snc), out))
        after = (out / "SNC MANAGEMENT & HOLDINGS LLC.pdf").stat().st_mtime
        print(f"  SNC file untouched: {before == after}")
        print("  3c. look for a real record whose history has no usable Initial Filing:")
        checked = 0
        for t in sorted([t for t in rows if t and rules.is_llc(t.entity_type)], key=lambda t: t.date)[:12]:
            if not t or not rules.is_llc(t.entity_type):
                continue
            fl = bz.history(t.record_num)
            pick = rules.pick_initial_filing(fl, t.entity_number)
            checked += 1
            types = ", ".join(sorted({x["AMENDMENT_TYPE"] for x in fl}))
            print(f"    {t.entity_name} ({t.entity_number}) {t.date}: {pick.skip_reason or 'OK'} | {types}")
            if pick.skip_reason:
                show("download_one", download_one(bz, store, as_row(t), out))
                break
            if checked >= 6:
                print("    (no natural case in the 6 oldest LLCs; offline tests cover it)")
                break
    print("\nhistory rows:", [tuple(r) for r in sqlite3.connect(db).execute(
        "SELECT entity_number, download_status, local_filename FROM downloads")])


if __name__ == "__main__":
    main()

