"""Import every module once so its tables and job handlers are registered."""
from .modules.domains import service as domains  # noqa: F401
from .modules.pdf import service as pdf  # noqa: F401
from .modules.websites import service as websites  # noqa: F401
from . import runtime_config  # noqa: F401  (stored_settings table)
from . import auth  # noqa: F401  (users, auth_sessions tables)
from . import selftest  # noqa: F401


SETUP_LOCK = 7_031_502  # any constant: PostgreSQL advisory lock id for start-up


def setup():
    """Tables + seed. The API and the worker start at the same time (Docker Compose, the start script): a
    session-level advisory lock makes them take turns, so the second one finds everything done instead of
    failing on duplicate keys."""
    from sqlalchemy import text

    from .db import engine, init_db, session_scope

    with engine().connect() as lock:
        lock.execute(text("SELECT pg_advisory_lock(:k)"), {"k": SETUP_LOCK})
        try:
            init_db()
            with session_scope() as s:
                domains.seed(s)
                from . import write_guard

                write_guard.relock(s, "Tự khoá: tiến trình vừa khởi động lại")  # a restart never keeps real writes open
        finally:
            lock.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": SETUP_LOCK})
