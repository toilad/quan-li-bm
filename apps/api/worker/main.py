"""Worker: processes queued jobs one at a time (per-nick serialisation is enforced in the queue).
Run: python -m worker.main"""
import sys
import threading
import time

from wg_core import jobs, registry
from wg_core.config import settings
from wg_core.db import session_scope


def _beat(stop: threading.Event):
    while not stop.is_set():
        try:
            with session_scope() as s:
                jobs.heartbeat(s)
        except Exception as e:  # noqa: BLE001 — the database may be restarting; try again next beat
            print(f"heartbeat error: {e}", flush=True)
        stop.wait(jobs.HEARTBEAT_SECONDS)


def _recover():
    with session_scope() as s:
        jobs.recover_stale(s)


def _ocr_loop(stop: threading.Event):
    """FAST mode only: a second thread that runs scan readings (OCR) and nothing else."""
    while not stop.is_set():
        try:
            if not jobs.run_one(kinds=("pdf_ocr_read",)):
                stop.wait(settings().worker_poll_seconds)
        except Exception as e:  # noqa: BLE001 — keep the thread alive; the job records its error
            print(f"ocr worker error: {e}", flush=True)
            stop.wait(5)


def main():
    registry.setup()
    stop = threading.Event()
    threading.Thread(target=_beat, args=(stop,), daemon=True).start()
    from wg_core.modules.pdf.ocr import ocr_threads, ocr_workers, perf_mode

    if ocr_workers() == 2:
        threading.Thread(target=_ocr_loop, args=(stop,), daemon=True).start()
    print(f"OCR: chế độ {perf_mode()} · {ocr_workers()} việc OCR cùng lúc · {ocr_threads()} luồng CPU mỗi việc", flush=True)
    _recover()
    last_recover = time.monotonic()
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Worker sẵn sàng.", flush=True)
    while True:
        try:
            if time.monotonic() - last_recover > jobs.HEARTBEAT_SECONDS:  # jobs of a worker that died meanwhile
                _recover()
                last_recover = time.monotonic()
            if not jobs.run_one():
                time.sleep(settings().worker_poll_seconds)
        except KeyboardInterrupt:
            stop.set()
            break
        except Exception as e:  # keep the worker alive; the job itself records its error
            print(f"worker error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
