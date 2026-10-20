"""TẢI PHÔI CALIFORNIA — desktop window (Tkinter).

Random 5 / tick up to 5 keywords -> Start Search (sequential, stops at ~60 targets)
-> Download 50 (sequential, stops at 50 successful PDFs). Playwright runs in one
worker thread; the window only reads a queue of progress messages.
"""
from __future__ import annotations

import json
import os
import queue
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from playwright.sync_api import sync_playwright

from . import jobs, rules
from .bizfile import Bizfile
from .keywords import KEYWORDS
from .store import DONE, FAILED, NOT_RUN, RUNNING, Store

SETTINGS = Path(os.environ["LOCALAPPDATA"]) / "CaPhoi" / "settings.json"
ICON = Path(__file__).resolve().parent.parent / "tai-phoi-california.ico"
STATUS_COLOR = {NOT_RUN: "#222222", RUNNING: "#b36b00", DONE: "#1a7f37", FAILED: "#c62828"}


def load_settings() -> dict:
    try:
        return json.loads(SETTINGS.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def save_settings(d: dict) -> None:
    try:
        SETTINGS.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS.write_text(json.dumps(d, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError:
        pass


class App:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.store = Store()
        self.store.ensure_keywords(KEYWORDS)
        self.q: queue.Queue = queue.Queue()
        self.worker: threading.Thread | None = None
        self.stop_flag = threading.Event()
        s = load_settings()

        root.title("Tải phôi California")
        root.geometry("900x720")
        root.minsize(760, 600)
        if ICON.exists():
            try:
                root.iconbitmap(str(ICON))
            except tk.TclError:
                pass

        # ---- header numbers ----
        top = ttk.Frame(root, padding=(12, 10, 12, 4))
        top.pack(fill="x")
        self.lbl_goal = ttk.Label(top, font=("Segoe UI", 11, "bold"))
        self.lbl_goal.pack(anchor="w")
        self.lbl_now = ttk.Label(top, font=("Segoe UI", 10))
        self.lbl_now.pack(anchor="w", pady=(2, 0))
        self.lbl_captcha = tk.Label(top, text="", fg="white", bg="#c62828", font=("Segoe UI", 12, "bold"))

        # ---- settings ----
        opt = ttk.Frame(root, padding=(12, 4))
        opt.pack(fill="x")
        ttk.Label(opt, text="Tên tối đa:").pack(side="left")
        self.max_len = tk.IntVar(value=int(s.get("max_len", rules.DEFAULT_MAX_NAME_LEN)))
        ttk.Spinbox(opt, from_=10, to=80, width=4, textvariable=self.max_len).pack(side="left", padx=(4, 14))
        self.active_only = tk.BooleanVar(value=bool(s.get("active_only", True)))
        ttk.Checkbutton(opt, text="Active Only", variable=self.active_only).pack(side="left", padx=(0, 14))
        ttk.Label(opt, text="Thư mục lưu PDF:").pack(side="left")
        self.out_dir = tk.StringVar(value=s.get("out_dir", ""))
        ttk.Entry(opt, textvariable=self.out_dir, width=38).pack(side="left", padx=4, fill="x", expand=True)
        ttk.Button(opt, text="Chọn…", command=self.pick_dir).pack(side="left")

        # ---- keywords ----
        kwf = ttk.LabelFrame(root, text=f"KEYWORDS ({len(KEYWORDS)}) — chọn tối đa {jobs.BATCH_SIZE}", padding=8)
        kwf.pack(fill="both", expand=False, padx=12, pady=6)
        grid = ttk.Frame(kwf)
        grid.pack(fill="x")
        self.kw_vars: dict[str, tk.BooleanVar] = {}
        self.kw_checks: dict[str, tk.Checkbutton] = {}
        for i, kw in enumerate(KEYWORDS):
            v = tk.BooleanVar(value=False)
            cb = tk.Checkbutton(grid, text=kw, variable=v, anchor="w", width=15,
                                command=lambda k=kw: self.on_tick(k))
            cb.grid(row=i // 6, column=i % 6, sticky="w")
            self.kw_vars[kw], self.kw_checks[kw] = v, cb
        bar = ttk.Frame(kwf)
        bar.pack(fill="x", pady=(8, 0))
        self.lbl_sel = ttk.Label(bar, text="")
        self.lbl_sel.pack(side="left")
        ttk.Button(bar, text="Reset keyword history", command=self.reset_history).pack(side="right")
        ttk.Button(bar, text="Bỏ chọn", command=self.clear_ticks).pack(side="right", padx=6)

        # ---- actions ----
        act = ttk.Frame(root, padding=(12, 2))
        act.pack(fill="x")
        self.btn_random = ttk.Button(act, text="Random 5", command=self.random5)
        self.btn_search = ttk.Button(act, text="Start Search", command=self.start_search)
        self.btn_dl = ttk.Button(act, text=f"Download {jobs.DAILY_DOWNLOAD_GOAL}", command=self.start_download)
        self.btn_stop = ttk.Button(act, text="Dừng", command=self.stop, state="disabled")
        for b in (self.btn_random, self.btn_search, self.btn_dl, self.btn_stop):
            b.pack(side="left", padx=(0, 8))

        # ---- log ----
        logf = ttk.Frame(root, padding=(12, 6, 12, 12))
        logf.pack(fill="both", expand=True)
        self.log = tk.Text(logf, height=12, font=("Consolas", 10), wrap="none", state="disabled")
        sb = ttk.Scrollbar(logf, command=self.log.yview)
        self.log.configure(yscrollcommand=sb.set)
        self.log.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")

        self.refresh()
        root.protocol("WM_DELETE_WINDOW", self.on_close)
        root.after(200, self.pump)

    # ---- helpers ----------------------------------------------------------
    def write(self, line: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", line + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")

    def selected(self) -> list[str]:
        return [k for k in KEYWORDS if self.kw_vars[k].get()]

    def refresh(self) -> None:
        pool, ok = self.store.pending_count(), self.store.ok_today()
        self.lbl_goal.configure(text=f"Mục tiêu hôm nay: {jobs.DAILY_DOWNLOAD_GOAL}     "
                                     f"Target đã tìm: {pool} / {jobs.POOL_GOAL}     "
                                     f"Đã tải: {ok} / {jobs.DAILY_DOWNLOAD_GOAL}")
        statuses = {r["keyword"]: r for r in self.store.keyword_rows()}
        for kw, cb in self.kw_checks.items():
            r = statuses.get(kw)
            st = r["status"] if r else NOT_RUN
            cb.configure(fg=STATUS_COLOR.get(st, "#222"))
        n_left = sum(1 for r in statuses.values() if r["status"] == NOT_RUN)
        self.lbl_sel.configure(text=f"Đã chọn: {len(self.selected())} / {jobs.BATCH_SIZE}"
                                    f"     (chưa chạy: {n_left}; xanh = DONE, đỏ = FAILED)")

    def busy(self, on: bool) -> None:
        for b in (self.btn_random, self.btn_search, self.btn_dl):
            b.configure(state="disabled" if on else "normal")
        self.btn_stop.configure(state="normal" if on else "disabled")

    def persist(self) -> None:
        save_settings({"max_len": self.max_len.get(), "active_only": self.active_only.get(),
                       "out_dir": self.out_dir.get()})

    # ---- keyword choice ---------------------------------------------------
    def on_tick(self, kw: str) -> None:
        if self.kw_vars[kw].get() and len(self.selected()) > jobs.BATCH_SIZE:
            self.kw_vars[kw].set(False)  # never a 6th keyword
        self.refresh()

    def clear_ticks(self) -> None:
        for v in self.kw_vars.values():
            v.set(False)
        self.refresh()

    def random5(self) -> None:
        batch = jobs.random_batch(self.store)
        self.clear_ticks()
        for k in batch:
            self.kw_vars[k].set(True)
        self.refresh()
        self.write("Random batch: " + ", ".join(f"{i}. {k}" for i, k in enumerate(batch, 1)))

    def reset_history(self) -> None:
        if messagebox.askyesno("Reset keyword history",
                               "Đặt lại tất cả keyword về NOT_RUN để chạy lại từ đầu?\n"
                               "(Không xoá lịch sử tải PDF, công ty đã tải vẫn không tải lại.)"):
            self.store.reset_keywords()
            self.refresh()
            self.write("Đã reset keyword history.")

    def pick_dir(self) -> None:
        d = filedialog.askdirectory(title="Chọn thư mục lưu PDF", initialdir=self.out_dir.get() or None)
        if d:
            self.out_dir.set(d)
            self.persist()

    # ---- jobs ---------------------------------------------------------------
    def start_search(self) -> None:
        kws = self.selected()
        if not kws:
            messagebox.showinfo("Start Search", "Chọn tối đa 5 keyword hoặc bấm Random 5.")
            return
        if self.store.pending_count() >= jobs.POOL_GOAL:
            messagebox.showinfo("Start Search", f"Đã đủ {jobs.POOL_GOAL} target, bấm Download.")
            return
        self.persist()
        max_len, active = self.max_len.get(), self.active_only.get()
        self.write(f"--- Search: {', '.join(kws)} (tên ≤ {max_len}, Active Only: {'bật' if active else 'tắt'})")
        self.run_worker(lambda bz: ("search", jobs.run_search(
            bz, self.store, kws, max_len=max_len, active_only=active,
            progress=lambda s: self.q.put(("progress", s)), should_stop=self.stop_flag.is_set)))

    def start_download(self) -> None:
        out = self.out_dir.get().strip()
        if not out:
            self.pick_dir()
            out = self.out_dir.get().strip()
            if not out:
                return
        if self.store.pending_count() == 0:
            messagebox.showinfo("Download", "Chưa có target. Bấm Random 5 rồi Start Search trước.")
            return
        self.persist()
        self.write(f"--- Download vào: {out}")
        self.run_worker(lambda bz: ("download", jobs.run_download(
            bz, self.store, Path(out), progress=lambda s: self.q.put(("progress", s)),
            should_stop=self.stop_flag.is_set)))

    def run_worker(self, job) -> None:
        self.stop_flag.clear()
        self.busy(True)

        def body():
            try:
                with sync_playwright() as pw:
                    bz = Bizfile(pw, notify=lambda kind, msg: self.q.put((kind, msg)),
                                 should_stop=self.stop_flag.is_set)
                    self.q.put(job(bz))
            except Exception as e:
                self.q.put(("error", str(e)))
            finally:
                self.q.put(("finished", None))

        self.worker = threading.Thread(target=body, daemon=True)
        self.worker.start()

    def stop(self) -> None:
        self.stop_flag.set()
        self.write("Đang dừng sau bước hiện tại…")

    # ---- queue pump (UI thread) --------------------------------------------
    def pump(self) -> None:
        try:
            while True:
                kind, data = self.q.get_nowait()
                self.handle(kind, data)
        except queue.Empty:
            pass
        self.root.after(200, self.pump)

    def handle(self, kind: str, data) -> None:
        if kind == "progress":
            s = data
            if s["phase"] == "search":
                self.lbl_now.configure(text=f"Keyword {s['index']} / {s['total']} — Đang tìm: {s['keyword']}"
                                            f"     Target: {s['pool']} / {s['pool_goal']}")
                d = s.get("done")
                if d:
                    self.write(f"{d['keyword']:<16}{d['status']:<8}raw {d['raw']:>4}   hợp lệ {d['valid']:>3}"
                               f"   mới {d['new']:>3}" + (f"   lỗi: {d['error'][:80]}" if d.get("error") else ""))
            else:
                self.lbl_now.configure(text=f"Đang tải: {s['current']}     Đã tải: {s['ok']} / {s['goal']}")
                last = s.get("last")
                if last:
                    self.write(f"{last['status']:<8}{last['name'][:34]:<36}{last['filename'] or ''}"
                               f"{'  — ' + last['note'] if last['status'] != 'OK' else ''}")
            self.refresh()
        elif kind == "captcha":
            self.lbl_captcha.configure(text="  CẦN XÁC MINH — tick ô xác minh trong cửa sổ Edge, app sẽ tự chạy tiếp  ")
            self.lbl_captcha.pack(anchor="w", pady=(6, 0))
            self.write(data)
            try:
                self.root.bell()
                self.root.deiconify()
            except tk.TclError:
                pass
        elif kind == "resumed":
            self.lbl_captcha.pack_forget()
            self.write(data)
        elif kind == "info":
            self.write(data)
        elif kind == "error":
            self.write(f"LỖI: {data}")
        elif kind == "search":
            pool = self.store.pending_count()
            self.write(f"Xong lượt search. Target unique trong pool: {pool} / {jobs.POOL_GOAL}")
            if pool < jobs.POOL_GOAL:
                self.write("Chưa đủ: bấm Random 5 rồi Start Search để chạy 5 keyword tiếp theo.")
            else:
                self.write(f"Đủ target. Bấm Download {jobs.DAILY_DOWNLOAD_GOAL}.")
            self.clear_ticks()
        elif kind == "download":
            ok = sum(1 for x in data["log"] if x["status"] == "OK")
            sk = sum(1 for x in data["log"] if x["status"] == "SKIPPED")
            er = sum(1 for x in data["log"] if x["status"] == "ERROR")
            self.write(f"Xong lượt tải: +{ok} OK, {sk} skip, {er} lỗi. Hôm nay: {data['ok_today']} / {data['goal']}")
            if data["ok_today"] < data["goal"] and self.store.pending_count() == 0:
                self.write("Hết target trong pool: chạy thêm Random 5 → Start Search rồi Download tiếp.")
        elif kind == "finished":
            self.lbl_captcha.pack_forget()
            self.busy(False)
            self.refresh()

    def on_close(self) -> None:
        if self.worker and self.worker.is_alive():
            if not messagebox.askyesno("Thoát", "Đang chạy. Dừng và thoát?"):
                return
            self.stop_flag.set()
        self.persist()
        self.root.destroy()


def main() -> None:
    root = tk.Tk()
    try:
        ttk.Style().theme_use("vista")
    except tk.TclError:
        pass
    App(root)
    root.mainloop()


if __name__ == "__main__":
    main()
