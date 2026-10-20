"""Small SQLite history: keywords run, target pool, downloads. PDFs never go in here."""
from __future__ import annotations

import os
import sqlite3
from datetime import datetime
from pathlib import Path

from .rules import Target

DB_PATH = Path(os.environ["LOCALAPPDATA"]) / "CaPhoi" / "ca_phoi.db"

NOT_RUN, RUNNING, DONE, FAILED = "NOT_RUN", "RUNNING", "DONE", "FAILED"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS keywords (
  keyword TEXT PRIMARY KEY, status TEXT NOT NULL DEFAULT 'NOT_RUN',
  last_run TEXT, raw_count INTEGER, valid_count INTEGER, new_count INTEGER, error TEXT);
CREATE TABLE IF NOT EXISTS targets (
  entity_number TEXT PRIMARY KEY, entity_name TEXT NOT NULL, date TEXT, status TEXT,
  entity_type TEXT, record_id INTEGER, record_num TEXT, keyword_source TEXT, found_at TEXT);
CREATE TABLE IF NOT EXISTS downloads (
  entity_number TEXT PRIMARY KEY, entity_name TEXT, keyword_source TEXT,
  download_date TEXT, download_status TEXT, local_filename TEXT, note TEXT);
"""

# download_status values
OK, SKIPPED, ERROR = "OK", "SKIPPED", "ERROR"


def now() -> str:
    return datetime.now().isoformat(timespec="seconds")


class Store:
    def __init__(self, path: Path = DB_PATH):
        path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(path, check_same_thread=False)
        self.db.row_factory = sqlite3.Row
        self.db.executescript(_SCHEMA)
        # a crash mid-keyword must not leave it RUNNING forever
        self.db.execute("UPDATE keywords SET status=? WHERE status=?", (FAILED, RUNNING))
        self.db.commit()

    # ---- keywords --------------------------------------------------------
    def ensure_keywords(self, keywords: list[str]) -> None:
        self.db.executemany("INSERT OR IGNORE INTO keywords(keyword) VALUES (?)", [(k,) for k in keywords])
        self.db.commit()

    def keyword_rows(self) -> list[sqlite3.Row]:
        return self.db.execute("SELECT * FROM keywords ORDER BY rowid").fetchall()

    def set_keyword(self, keyword: str, status: str, **fields) -> None:
        cols = {"status": status, "last_run": now(), **fields}
        sets = ", ".join(f"{k}=?" for k in cols)
        self.db.execute(f"UPDATE keywords SET {sets} WHERE keyword=?", (*cols.values(), keyword))
        self.db.commit()

    def reset_keywords(self) -> None:
        self.db.execute("UPDATE keywords SET status='NOT_RUN', last_run=NULL, raw_count=NULL,"
                        " valid_count=NULL, new_count=NULL, error=NULL")
        self.db.commit()

    # ---- target pool -----------------------------------------------------
    def add_target(self, t: Target, keyword: str) -> bool:
        """True when new (not in pool, never downloaded or skipped before)."""
        if self.db.execute("SELECT 1 FROM downloads WHERE entity_number=? AND download_status!='ERROR'",
                           (t.entity_number,)).fetchone():
            return False
        cur = self.db.execute(
            "INSERT OR IGNORE INTO targets VALUES (?,?,?,?,?,?,?,?,?)",
            (t.entity_number, t.entity_name, t.date, t.status, t.entity_type, t.record_id,
             t.record_num, keyword, now()))
        self.db.commit()
        return cur.rowcount == 1

    def pending_targets(self) -> list[sqlite3.Row]:
        """Pool entries not downloaded/skipped yet, oldest first. An ERROR is retried on a later day."""
        day = datetime.now().date().isoformat()
        return self.db.execute(
            "SELECT t.* FROM targets t LEFT JOIN downloads d USING(entity_number)"
            " WHERE d.entity_number IS NULL"
            "    OR (d.download_status='ERROR' AND substr(d.download_date,1,10) < ?)"
            " ORDER BY t.found_at, t.rowid", (day,)).fetchall()

    def pending_count(self) -> int:
        return len(self.pending_targets())

    # ---- downloads -------------------------------------------------------
    def download_of(self, entity_number: str) -> sqlite3.Row | None:
        return self.db.execute("SELECT * FROM downloads WHERE entity_number=?", (entity_number,)).fetchone()

    def entity_for_filename(self, filename: str) -> str | None:
        r = self.db.execute("SELECT entity_number FROM downloads WHERE local_filename=? AND download_status='OK'",
                            (filename,)).fetchone()
        return r["entity_number"] if r else None

    def record_download(self, entity_number: str, entity_name: str, keyword: str | None,
                        status: str, filename: str | None, note: str | None) -> None:
        self.db.execute("INSERT OR REPLACE INTO downloads VALUES (?,?,?,?,?,?,?)",
                        (entity_number, entity_name, keyword, now(), status, filename, note))
        self.db.commit()

    def ok_today(self) -> int:
        day = datetime.now().date().isoformat()
        return self.db.execute("SELECT COUNT(*) FROM downloads WHERE download_status='OK'"
                               " AND substr(download_date,1,10)=?", (day,)).fetchone()[0]
