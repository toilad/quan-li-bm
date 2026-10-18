"""Owner login for the web app and API.

- Passwords: scrypt (Python standard library) with a random salt per user; never stored or logged in clear.
- Sessions: a random token in an HttpOnly cookie; the database keeps only its SHA-256.
  Ends after 24 h without use or 7 days in total, or on logout / password change.
- Failed logins are throttled per client address.
"""
import base64
import hashlib
import hmac
import secrets
import time
from datetime import datetime, timedelta, timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, delete, func, select
from sqlalchemy.orm import Mapped, Session, mapped_column

from .db import Base

COOKIE = "qlbm_session"
IDLE = timedelta(hours=24)
MAX_AGE = timedelta(days=7)
# A login made on the machine that runs the app (loopback, not through a proxy) may stay longer: the owner's own PC.
# Everything else (other devices, anything behind a reverse proxy) keeps 24 h idle / 7 days.
LOCAL_IDLE = timedelta(days=7)
LOCAL_MAX_AGE = timedelta(days=30)
LOCAL_TAG = "local:"


def limits(ip: str) -> tuple[timedelta, timedelta]:
    """(idle, max age) for a session by where it was created (AuthSession.ip, set at login)."""
    return (LOCAL_IDLE, LOCAL_MAX_AGE) if (ip or "").startswith(LOCAL_TAG) else (IDLE, MAX_AGE)
MIN_PASSWORD = 10
_N, _R, _P = 2**14, 8, 1
_DUMMY = None


class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), unique=True)
    pw_hash: Mapped[str] = mapped_column(String(300))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuthSession(Base):
    __tablename__ = "auth_sessions"
    id: Mapped[int] = mapped_column(primary_key=True)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id", ondelete="CASCADE"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    ip: Mapped[str] = mapped_column(String(64), default="")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    dk = hashlib.scrypt(password.encode(), salt=salt, n=_N, r=_R, p=_P, dklen=32)
    return f"scrypt${_N}${_R}${_P}${base64.b64encode(salt).decode()}${base64.b64encode(dk).decode()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, n, r, p, salt, dk = stored.split("$")
        got = hashlib.scrypt(password.encode(), salt=base64.b64decode(salt), n=int(n), r=int(r), p=int(p), dklen=32)
        return hmac.compare_digest(got, base64.b64decode(dk))
    except (ValueError, TypeError):
        return False


def _token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def check_new_password(username: str, password: str):
    if len(password) < MIN_PASSWORD:
        raise ValueError(f"Mật khẩu tối thiểu {MIN_PASSWORD} ký tự")
    if username and username.lower() in password.lower():
        raise ValueError("Mật khẩu không được chứa tên đăng nhập")


def users_exist(s: Session) -> bool:
    return s.scalar(select(func.count(User.id))) > 0


def create_user(s: Session, username: str, password: str) -> User:
    username = username.strip().lower()
    if not username or not username.replace(".", "").replace("-", "").replace("_", "").isalnum() or len(username) > 64:
        raise ValueError("Tên đăng nhập chỉ gồm chữ, số, “.”, “-”, “_”")
    if s.scalar(select(User).where(User.username == username)):
        raise ValueError("Tên đăng nhập đã có")
    check_new_password(username, password)
    u = User(username=username, pw_hash=hash_password(password))
    s.add(u)
    s.flush()
    return u


def set_password(s: Session, user: User, password: str):
    check_new_password(user.username, password)
    user.pw_hash = hash_password(password)
    s.execute(delete(AuthSession).where(AuthSession.user_id == user.id))  # every other session ends


def login(s: Session, username: str, password: str, ip: str = "", local: bool = False) -> str | None:
    global _DUMMY
    u = s.scalar(select(User).where(User.username == username.strip().lower()))
    if not u:
        _DUMMY = _DUMMY or hash_password(secrets.token_hex(8))
        verify_password(password, _DUMMY)  # same cost whether or not the user exists
        return None
    if not verify_password(password, u.pw_hash):
        return None
    token = secrets.token_urlsafe(32)
    now = _now()
    s.add(AuthSession(token_hash=_token_hash(token), user_id=u.id, created_at=now, last_seen=now,
                      ip=((LOCAL_TAG if local else "") + ip)[:64]))
    u.last_login = now
    return token


def session_user(s: Session, token: str | None) -> User | None:
    if not token:
        return None
    row = s.scalar(select(AuthSession).where(AuthSession.token_hash == _token_hash(token)))
    if not row:
        return None
    now = _now()
    idle, max_age = limits(row.ip)
    if now - row.last_seen > idle or now - row.created_at > max_age:
        s.delete(row)
        return None
    if now - row.last_seen > timedelta(minutes=5):
        row.last_seen = now
    return s.get(User, row.user_id)


def logout(s: Session, token: str | None):
    if token:
        s.execute(delete(AuthSession).where(AuthSession.token_hash == _token_hash(token)))


class Throttle:
    """At most `limit` failed logins per address in `window` seconds (single API process)."""

    def __init__(self, limit: int = 8, window: int = 900):
        self.limit, self.window, self.fails = limit, window, {}

    def blocked(self, key: str) -> int:
        now = time.monotonic()
        recent = [t for t in self.fails.get(key, []) if now - t < self.window]
        self.fails[key] = recent
        return int(self.window - (now - recent[0])) if len(recent) >= self.limit else 0

    def fail(self, key: str):
        self.fails.setdefault(key, []).append(time.monotonic())

    def reset(self, key: str):
        self.fails.pop(key, None)


throttle = Throttle()
