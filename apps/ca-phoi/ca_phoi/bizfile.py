"""California Bizfile through a real, installed Edge window.

Every request is a fetch() run inside the Bizfile page, so it carries the
session the owner verified. One request at a time with a pause between them.
When Imperva asks for a check, the job pauses, tells the owner ("CẦN XÁC MINH"),
waits until the owner has ticked it in the Edge window, then retries the same
request. Nothing here tries to solve or bypass the check.
"""
from __future__ import annotations

import base64
import json
import os
import random
import subprocess
import time
import urllib.request
from pathlib import Path
from typing import Callable

from playwright.sync_api import Page, Playwright

BASE = "https://bizfileonline.sos.ca.gov"
SEARCH_URL = f"{BASE}/search/business"
EDGE_EXE = Path(os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)")) / "Microsoft/Edge/Application/msedge.exe"
EDGE_PROFILE = Path(os.environ["LOCALAPPDATA"]) / "CaPhoi" / "edge-profile"
CDP_PORT = 9333
CDP_URL = f"http://127.0.0.1:{CDP_PORT}"
DELAY_S = (2.5, 4.0)
CAPTCHA_WAIT_S = 20 * 60

SEARCH_BODY = {
    "SEARCH_VALUE": "", "SEARCH_FILTER_TYPE_ID": "1", "SEARCH_TYPE_ID": "1",
    "FILING_TYPE_ID": "", "STATUS_ID": "", "FILING_DATE": {"start": None, "end": None},
    "CORPORATION_BANKRUPTCY_YN": False, "CORPORATION_LEGAL_PROCEEDINGS_YN": False,
    "OFFICER_OBJECT": {"FIRST_NAME": "", "MIDDLE_NAME": "", "LAST_NAME": ""},
    "NUMBER_OF_FEMALE_DIRECTORS": "99", "NUMBER_OF_UNDERREPRESENTED_DIRECTORS": "99",
    "COMPENSATION_FROM": "", "COMPENSATION_TO": "", "SHARES_YN": False, "OPTIONS_YN": False,
    "BANKRUPTCY_YN": False, "FRAUD_YN": False, "LOANS_YN": False, "AUDITOR_NAME": "",
}

# Headers copy the site's own app: it always sends "Authorization: undefined",
# and /api/History answers 400 ("key" null) without it.
_FETCH_JS = """
async ([url, method, body, binary]) => {
  const opt = {method, headers: {'Accept': '*/*', 'Authorization': 'undefined'}};
  if (body !== null) { opt.headers['Content-Type'] = 'application/json'; opt.body = body; }
  const r = await fetch(url, opt);
  const ct = r.headers.get('content-type') || '';
  if (binary && !ct.includes('text/html')) {
    const buf = new Uint8Array(await r.arrayBuffer());
    let s = ''; for (let i = 0; i < buf.length; i += 0x8000) s += String.fromCharCode(...buf.subarray(i, i + 0x8000));
    return {status: r.status, ct, b64: btoa(s)};
  }
  return {status: r.status, ct, text: await r.text()};
}
"""

Notify = Callable[[str, str], None]  # (kind, message); kind: "info" | "captcha" | "resumed"


class BizfileError(Exception):
    pass


def _cdp_up() -> bool:
    try:
        urllib.request.urlopen(f"{CDP_URL}/json/version", timeout=2).read()
        return True
    except OSError:
        return False


def open_edge() -> None:
    """Start the installed Edge with the app's own profile (keeps the verified session)."""
    if _cdp_up():
        return
    EDGE_PROFILE.mkdir(parents=True, exist_ok=True)
    subprocess.Popen([str(EDGE_EXE), f"--remote-debugging-port={CDP_PORT}",
                      f"--user-data-dir={EDGE_PROFILE}", "--no-first-run",
                      "--no-default-browser-check", SEARCH_URL])
    for _ in range(30):
        time.sleep(1)
        if _cdp_up():
            return
    raise BizfileError("Không mở được Edge (cổng điều khiển không lên).")


class Bizfile:
    def __init__(self, pw: Playwright, notify: Notify | None = None,
                 should_stop: Callable[[], bool] | None = None):
        self.notify = notify or (lambda kind, msg: print(kind.upper(), msg, flush=True))
        self.should_stop = should_stop or (lambda: False)
        open_edge()
        ctx = pw.chromium.connect_over_cdp(CDP_URL).contexts[0]
        self.page: Page = next((p for p in ctx.pages if p.url.startswith(BASE)), None) or ctx.new_page()
        if not self.page.url.startswith(BASE) or self._captcha_visible():
            self._wait_for_human()

    # ---- CAPTCHA -------------------------------------------------------
    def _captcha_visible(self) -> bool:
        for fr in self.page.frames:
            try:
                if "Additional security check" in fr.inner_text("body", timeout=1500):
                    return True
            except Exception:
                pass
        return False

    def _wait_for_human(self) -> None:
        self.page.goto(SEARCH_URL)
        self.page.wait_for_timeout(2500)
        if not self._captcha_visible():
            return
        self.page.bring_to_front()
        self.notify("captcha", "CẦN XÁC MINH: tick ô xác minh trong cửa sổ Edge, app sẽ tự chạy tiếp.")
        deadline = time.time() + CAPTCHA_WAIT_S
        while time.time() < deadline:
            if self.should_stop():
                raise BizfileError("Đã dừng trong lúc chờ xác minh.")
            self.page.wait_for_timeout(3000)
            if not self._captcha_visible() and self.page.locator("input").count() > 0:
                self.notify("resumed", "Đã xác minh, chạy tiếp.")
                return
        raise BizfileError("Hết thời gian chờ xác minh.")

    # ---- requests ------------------------------------------------------
    def _call(self, path: str, *, post: dict | None = None, binary: bool = False) -> dict:
        for attempt in range(3):
            r = self.page.evaluate(_FETCH_JS, [path, "POST" if post is not None else "GET",
                                               json.dumps(post) if post is not None else None, binary])
            time.sleep(random.uniform(*DELAY_S))
            if "text/html" not in r["ct"] and r["status"] not in (403, 429):
                return r
            if r["status"] == 429:
                self.notify("info", "Bizfile báo gửi quá nhanh, chờ 2 phút.")
                time.sleep(120)
            else:
                self._wait_for_human()
        raise BizfileError(f"Bị chặn liên tục tại {path[:60]}")

    def _json(self, path: str, **kw) -> dict:
        r = self._call(path, **kw)
        if r["status"] != 200:
            raise BizfileError(f"HTTP {r['status']} tại {path[:60]}: {r.get('text', '')[:150]}")
        return json.loads(r["text"])

    def search(self, value: str, *, date_from: str | None = None, date_to: str | None = None) -> list[dict]:
        """Raw rows (Bizfile returns at most 500). Dates are mm/dd/yyyy."""
        body = {**SEARCH_BODY, "SEARCH_VALUE": value,
                "FILING_DATE": {"start": date_from, "end": date_to}}
        return list(self._json("/api/Records/businesssearch", post=body).get("rows", {}).values())

    def history(self, record_num: str) -> list[dict]:
        return self._json(f"/api/History/business/{record_num}").get("AMENDMENT_LIST") or []

    def download(self, link: str) -> bytes:
        r = self._call(link, binary=True)
        if r["status"] != 200 or "b64" not in r:
            raise BizfileError(f"Tải PDF lỗi HTTP {r['status']}")
        data = base64.b64decode(r["b64"])
        if not data.startswith(b"%PDF"):
            raise BizfileError(f"Không phải PDF ({r['ct']}, {len(data)} bytes)")
        return data
