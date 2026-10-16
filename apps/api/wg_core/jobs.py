"""PostgreSQL job queue.

- enqueue(): one live job per idempotency key (partial unique index) → no double runs.
- claim(): SELECT … FOR UPDATE SKIP LOCKED, and at most one running job per `resource` (e.g. a nick).
- run_one(): calls the handler for the job kind. Handlers advance `job.state` step by step and commit
  after each step, so a crash or retry resumes exactly where it stopped.
- Error mapping: NotConfigured/NotAvailable → blocked, Transient → retry with backoff,
  Conflict → conflict, anything else → failed. Nothing is ever reported as done unless the handler returned.
"""
import socket
import traceback
from datetime import datetime, timedelta, timezone
from typing import Callable

from sqlalchemy import select, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from .db import session_scope
from .integrations.errors import Conflict, NotAvailable, NotConfigured, Transient
from .models import Job, JobLog

WORKER_ID = f"{socket.gethostname()}"
HANDLERS: dict[str, Callable[["JobContext"], None]] = {}


def handler(kind: str):
    def deco(fn):
        HANDLERS[kind] = fn
        return fn

    return deco


class JobContext:
    """What a handler gets: the job, a log function and a checkpoint() that persists state immediately."""

    def __init__(self, session: Session, job: Job):
        self.session, self.job = session, job

    @property
    def state(self) -> dict:
        if self.job.state is None:
            self.job.state = {}
        return self.job.state

    def log(self, message: str, level: str = "info"):
        self.session.add(JobLog(job_id=self.job.id, level=level, message=message))
        self.session.flush()

    def step(self, name: str):
        self.job.step = name
        self.checkpoint()

    def checkpoint(self, **updates):
        self.state.update(updates)  # same dict object: handlers holding ctx.state see the change
        flag_modified(self.job, "state")
        self.session.commit()


def enqueue(session: Session, kind: str, idem_key: str, payload: dict, resource: str | None = None,
            max_attempts: int = 5) -> tuple[Job, bool]:
    """Returns (job, created). If a live job with the same key exists, it is returned instead."""
    live = session.scalar(select(Job).where(Job.idem_key == idem_key, Job.status.in_(("queued", "running"))))
    if live:
        return live, False
    job = Job(kind=kind, idem_key=idem_key, payload=payload, resource=resource, max_attempts=max_attempts, state={})
    session.add(job)
    try:
        session.flush()
    except IntegrityError:  # raced with another enqueue
        session.rollback()
        return session.scalar(select(Job).where(Job.idem_key == idem_key, Job.status.in_(("queued", "running")))), False
    return job, True


def retry(session: Session, job_id: int) -> Job:
    """Re-queue a failed/blocked job. Its state (finished steps) is kept."""
    job = session.get(Job, job_id)
    if job and job.status in ("failed", "blocked"):
        job.status, job.run_after, job.last_error = "queued", datetime.now(timezone.utc), None
        job.attempts = 0
        session.add(JobLog(job_id=job.id, level="info", message=f"Thử lại từ bước “{job.step or 'đầu'}” — bước đã xong được giữ"))
    return job


def claim(session: Session) -> Job | None:
    row = session.execute(text("""
        SELECT id FROM jobs j
        WHERE j.status = 'queued' AND j.run_after <= now()
          AND (j.resource IS NULL OR NOT EXISTS (
                SELECT 1 FROM jobs r WHERE r.resource = j.resource AND r.status = 'running'))
        ORDER BY j.run_after, j.id
        FOR UPDATE SKIP LOCKED
        LIMIT 1
    """)).first()
    if not row:
        return None
    job = session.get(Job, row[0])
    job.status, job.locked_by, job.locked_at = "running", WORKER_ID, datetime.now(timezone.utc)
    job.attempts += 1
    session.commit()
    return job


def run_one() -> bool:
    """Claim and run one job. Returns False when the queue is empty."""
    with session_scope() as s:
        job = claim(s)
        if not job:
            return False
        ctx = JobContext(s, job)
        fn = HANDLERS.get(job.kind)
        try:
            if not fn:
                raise RuntimeError(f"Không có handler cho loại việc {job.kind}")
            fn(ctx)
            job.status, job.last_error = "done", None
            if job.state.get("outcome") == "conflict":
                job.status = "conflict"
        except (NotConfigured, NotAvailable) as e:
            job.status, job.last_error = "blocked", str(e)
            ctx.log(str(e), "err")
        except Conflict as e:
            job.status, job.last_error = "conflict", str(e)
            ctx.log(str(e), "warn")
        except Transient as e:
            if job.attempts < job.max_attempts:
                delay = e.retry_after or min(900, 15 * 2 ** (job.attempts - 1))
                job.status, job.last_error = "queued", str(e)
                job.run_after = datetime.now(timezone.utc) + timedelta(seconds=delay)
                ctx.log(f"Lỗi tạm thời, tự thử lại sau {int(delay)}s: {e}", "warn")
            else:
                job.status, job.last_error = "failed", str(e)
                ctx.log(f"Hết số lần thử: {e}", "err")
        except Exception as e:  # noqa: BLE001 — recorded, never swallowed silently
            job.status, job.last_error = "failed", f"{type(e).__name__}: {e}"
            ctx.log(job.last_error, "err")
            ctx.log(traceback.format_exc(limit=3), "info")
        job.locked_by = None
        return True


def recover_stale(session: Session, minutes: int = 30):
    """Jobs left 'running' by a crashed worker go back to the queue (state kept → resume)."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    for job in session.scalars(select(Job).where(Job.status == "running", Job.locked_at < cutoff)):
        job.status, job.locked_by = "queued", None
        session.add(JobLog(job_id=job.id, level="warn", message="Worker dừng giữa chừng — đưa lại vào hàng đợi, giữ các bước đã xong"))
