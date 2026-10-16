"""Import every module once so its tables and job handlers are registered."""
from .modules.domains import service as domains  # noqa: F401
from .modules.pdf import service as pdf  # noqa: F401
from .modules.websites import service as websites  # noqa: F401


def setup():
    from .db import init_db, session_scope

    init_db()
    with session_scope() as s:
        domains.seed(s)
