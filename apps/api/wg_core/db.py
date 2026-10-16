"""Database engine/session. Production uses DATABASE_URL (PostgreSQL in Docker);
local dev falls back to an embedded PostgreSQL in apps/api/.pgdata (wg_core.devdb)."""
from contextlib import contextmanager
from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def database_url() -> str:
    url = settings().database_url
    if not url:
        from .devdb import dev_database_url

        url = dev_database_url()
    if url.startswith("postgresql://"):
        url = "postgresql+psycopg://" + url[len("postgresql://"):]
    return url


@lru_cache
def engine():
    return create_engine(database_url(), pool_pre_ping=True, future=True)


@lru_cache
def _factory():
    return sessionmaker(bind=engine(), expire_on_commit=False)


@contextmanager
def session_scope() -> Session:
    s = _factory()()
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def init_db():
    from . import models  # noqa: F401  (register tables)

    Base.metadata.create_all(engine())
