"""Embedded PostgreSQL for local development only (pgserver bundles the PostgreSQL 16 binaries).
Data stays in apps/api/.pgdata (gitignored). Production uses the postgres service in docker-compose."""
from functools import lru_cache

from .config import API_ROOT


@lru_cache
def _server():
    import pgserver  # dev dependency

    path = API_ROOT / ".pgdata"
    path.mkdir(exist_ok=True)
    return pgserver.get_server(str(path), cleanup_mode=None)


def dev_database_url() -> str:
    srv = _server()
    out = srv.psql("SELECT datname FROM pg_database WHERE datname='qlbm';")
    if "qlbm" not in out:
        srv.psql("CREATE DATABASE qlbm;")
    return srv.get_uri("qlbm")
