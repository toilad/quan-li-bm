"""Embedded PostgreSQL for local development only (pgserver bundles the PostgreSQL 16 binaries).
Data stays in apps/api/.pgdata (gitignored). Production uses the postgres service in docker-compose."""
from functools import lru_cache

from .config import API_ROOT


@lru_cache
def _server():
    import time

    import pgserver  # dev dependency

    path = API_ROOT / ".pgdata"
    path.mkdir(exist_ok=True)
    # pgserver waits only 10 s for pg_ctl. After the PC was switched off without stopping PostgreSQL, crash recovery
    # takes longer (seen 2026-10-18: ~40 s, retrying on a "sharing violation" for the log file inside .pgdata) and the
    # first call times out although the server comes up. Keep asking for up to 2 minutes: once it is running,
    # get_server attaches to it.
    deadline = time.monotonic() + 120
    while True:
        try:
            return pgserver.get_server(str(path), cleanup_mode=None)
        except Exception:
            if time.monotonic() > deadline:
                raise
            time.sleep(5)


def dev_database_url() -> str:
    srv = _server()
    out = srv.psql("SELECT datname FROM pg_database WHERE datname='qlbm';")
    if "qlbm" not in out:
        srv.psql("CREATE DATABASE qlbm;")
    return srv.get_uri("qlbm")
