"""Queue behaviour with fake data: dedupe, pause between steps, automatic retry, manual retry, crash recovery."""
from datetime import datetime, timedelta, timezone

from tests.conftest import drain
from wg_core import jobs
from wg_core.db import session_scope
from wg_core.models import AppSetting, Job


def _job(key="a", **payload):
    with session_scope() as s:
        job, created = jobs.enqueue(s, "selftest", f"selftest:{key}", {"steps": 3, "sleep": 0, "fail_once_at": None, **payload}, resource="selftest")
        return job.id, created


def _get(job_id):
    with session_scope() as s:
        j = s.get(Job, job_id)
        return j.status, dict(j.state or {})


def test_same_key_is_one_live_job():
    a, ca = _job("x")
    b, cb = _job("x")
    assert a == b and ca and not cb
    drain()
    c, cc = _job("x")  # finished → a new run is allowed
    assert cc and c != a


def test_transient_failure_retries_and_each_step_runs_once():
    jid, _ = _job("t", fail_once_at=2)
    drain()  # runs step 1, fails at 2 → queued with a short delay
    st, state = _get(jid)
    assert st == "queued" and state["done"] == [1] and state["failed_once"]
    with session_scope() as s:
        s.get(Job, jid).run_after = datetime.now(timezone.utc)
    drain()
    st, state = _get(jid)
    assert st == "done" and state["done"] == [1, 2, 3] and state["runs"] == {"1": 1, "2": 1, "3": 1}


def test_pause_holds_queue_and_resume_continues():
    with session_scope() as s:
        jobs.set_paused(s, "selftest", True)
    jid, _ = _job("p")
    assert drain() == 0 and _get(jid)[0] == "queued"  # paused kind is not claimed
    with session_scope() as s:
        jobs.set_paused(s, "selftest", False)
    drain()
    assert _get(jid)[0] == "done"


def test_pause_during_a_job_stops_before_next_step(monkeypatch):
    jid, _ = _job("m", steps=3)
    import wg_core.selftest as st_mod

    real_sleep = st_mod.time.sleep

    def pause_after_first(_):
        with session_scope() as s:
            jobs.set_paused(s, "selftest", True)
        monkeypatch.setattr(st_mod.time, "sleep", real_sleep)

    monkeypatch.setattr(st_mod.time, "sleep", pause_after_first)
    drain()
    status, state = _get(jid)
    assert status == "queued" and state["done"] == [1]  # step 1 finished, then held
    with session_scope() as s:
        jobs.set_paused(s, "selftest", False)
    drain()
    status, state = _get(jid)
    assert status == "done" and state["runs"] == {"1": 1, "2": 1, "3": 1}


def test_manual_retry_keeps_finished_steps():
    jid, _ = _job("r", steps=2)
    with session_scope() as s:
        j = s.get(Job, jid)
        j.status, j.state, j.step = "failed", {"done": [1], "runs": {"1": 1}}, "Bước thử 2"
    with session_scope() as s:
        jobs.retry(s, jid)
    drain()
    status, state = _get(jid)
    assert status == "done" and state["runs"] == {"1": 1, "2": 1}


def test_worker_crash_recovery_resumes():
    jid, _ = _job("c", steps=2)
    with session_scope() as s:  # simulate a worker that died mid-job 40 minutes ago
        j = s.get(Job, jid)
        j.status, j.locked_at, j.state = "running", datetime.now(timezone.utc) - timedelta(minutes=40), {"done": [1], "runs": {"1": 1}}
    with session_scope() as s:
        jobs.recover_stale(s)
    drain()
    status, state = _get(jid)
    assert status == "done" and state["runs"] == {"1": 1, "2": 1}


def test_job_of_a_dead_worker_is_recovered_within_a_minute_but_a_live_one_is_left_alone():
    dead, _ = _job("dead", steps=1)
    live, _ = _job("live", steps=1)
    now = datetime.now(timezone.utc)
    with session_scope() as s:
        jobs.heartbeat(s, "other-host:1:alive")
        s.add(AppSetting(key="worker:other-host:2:dead", value={"at": (now - timedelta(seconds=90)).isoformat()}))
        for jid, wid in ((dead, "other-host:2:dead"), (live, "other-host:1:alive")):
            j = s.get(Job, jid)
            j.status, j.locked_by, j.locked_at = "running", wid, now - timedelta(minutes=2)  # killed 2 minutes ago
    with session_scope() as s:
        jobs.recover_stale(s)
    with session_scope() as s:
        assert s.get(Job, dead).status == "queued"  # its worker stopped beating → back in the queue
        assert s.get(Job, live).status == "running"  # its worker is still alive → untouched


def test_the_extra_ocr_thread_claims_only_scan_readings():
    with session_scope() as s:
        jobs.enqueue(s, "selftest_other", "q-other", {})
        jobs.enqueue(s, "pdf_ocr_read", "q-ocr", {"doc_id": 0}, resource="ocr:1")
    with session_scope() as s:
        job = jobs.claim(s, kinds=("pdf_ocr_read",))
        assert job.kind == "pdf_ocr_read"
        assert jobs.claim(s, kinds=("pdf_ocr_read",)) is None  # the other kind is left for the main loop


def test_ocr_never_takes_every_core(monkeypatch):
    import os

    from wg_core.modules.pdf import ocr

    monkeypatch.setattr(os, "cpu_count", lambda: 16)
    monkeypatch.setenv("OCR_PERFORMANCE_MODE", "NORMAL")
    assert ocr.perf_mode() == "NORMAL" and ocr.ocr_workers() == 1 and ocr.ocr_threads() == 4
    monkeypatch.setenv("OCR_PERFORMANCE_MODE", "FAST")
    assert ocr.ocr_workers() == 2 and ocr.ocr_workers() * ocr.ocr_threads() <= 16 // 2
    monkeypatch.setattr(os, "cpu_count", lambda: 4)
    assert ocr.ocr_workers() == 1 and ocr.ocr_threads() == 1  # a small PC: FAST stays one job, one thread
    monkeypatch.setenv("OCR_PERFORMANCE_MODE", "TURBO")
    assert ocr.perf_mode() == "NORMAL"
