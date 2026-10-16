"""Harmless job kind for checking the queue end to end with fake data (no external call).

payload: {"steps": 3, "sleep": 0.5, "fail_once_at": 2 | None}
state:   {"done": [1, 2, …], "runs": {"1": 1, …}, "failed_once": bool}
A correct queue runs every step exactly once, even with a transient failure, a pause or a worker restart.
"""
import time

from .integrations.errors import Transient
from .jobs import JobContext, handler


@handler("selftest")
def _selftest(ctx: JobContext):
    p, st = ctx.job.payload, ctx.state
    for i in range(1, int(p.get("steps", 3)) + 1):
        if i in st.get("done", []):
            continue
        ctx.step(f"Bước thử {i}")
        if p.get("fail_once_at") == i and not st.get("failed_once"):
            ctx.checkpoint(failed_once=True)
            raise Transient(f"lỗi giả lập ở bước {i}", retry_after=0.1)
        time.sleep(float(p.get("sleep", 0)))
        runs = dict(st.get("runs", {}))
        runs[str(i)] = runs.get(str(i), 0) + 1
        ctx.checkpoint(done=st.get("done", []) + [i], runs=runs)
        ctx.log(f"Xong bước thử {i}", "ok")
