"""Worker: processes queued jobs one at a time (per-nick serialisation is enforced in the queue).
Run: python -m worker.main"""
import sys
import time

from wg_core import jobs, registry
from wg_core.config import settings
from wg_core.db import session_scope


def main():
    registry.setup()
    with session_scope() as s:
        jobs.recover_stale(s)
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Worker sẵn sàng.", flush=True)
    while True:
        try:
            if not jobs.run_one():
                time.sleep(settings().worker_poll_seconds)
        except KeyboardInterrupt:
            break
        except Exception as e:  # keep the worker alive; the job itself records its error
            print(f"worker error: {e}", flush=True)
            time.sleep(5)


if __name__ == "__main__":
    main()
