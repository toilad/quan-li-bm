"""Configuration the owner sets from the “Cài đặt API” page, stored server-side.

- Secrets (API keys, tokens, OAuth client/refresh token) are encrypted with Fernet before they reach PostgreSQL.
  The encryption key is QLBM_MASTER_KEY (env) or, if unset, data/master.key created on first use — it is never in the
  database, never in Git, and excluded from data backups: keep a copy in a password manager.
- Values set here win over the environment / .env (which keeps working as before).
- Nothing here ever returns a secret to the API layer except get() for the integrations themselves.
"""
import os
import time
from datetime import datetime, timezone

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .config import _read_env_file, settings
from .db import Base


class StoredSetting(Base):
    __tablename__ = "stored_settings"
    name: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[str] = mapped_column(Text)  # Fernet token for secrets, plain text otherwise
    secret: Mapped[bool] = mapped_column(default=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))


NICKS = ("N1", "N2", "N3")
# name → (group, label, secret)
FIELDS: dict[str, tuple[str, str, bool]] = {
    "SHEET_ID": ("google", "ID Google Sheet", False),
    "SHEET_TAB": ("google", "Tab ghi dữ liệu", False),
    "SHEET_FIRST_ROW": ("google", "Dòng bắt đầu dữ liệu (trên đó là tiêu đề / ghi chú, app bỏ qua)", False),
    "DRIVE_FOLDER_ID": ("google", "ID thư mục Drive (trống → app tự tạo)", False),
    "GOOGLE_CLIENT_ID": ("google", "OAuth Client ID (…apps.googleusercontent.com)", False),
    "GOOGLE_CLIENT_SECRET": ("google", "OAuth Client secret (bấm 📋 cạnh mã trên Google Cloud rồi dán vào đây)", True),
    "GOOGLE_OAUTH_CLIENT_JSON": ("google", "Hoặc: cả file JSON OAuth client", True),
    "GOOGLE_TOKEN": ("google", "Quyền truy cập Google (cấp qua nút Kết nối)", True),
    "ANTHROPIC_API_KEY": ("ai", "Khoá API Anthropic", True),
    "AI_MODEL": ("ai", "Model", False),
    "PEXELS_API_KEY": ("photos", "Khoá API Pexels", True),
    "PIXABAY_API_KEY": ("photos", "Khoá API Pixabay", True),
    "PUBLIC_API_URL": ("server", "Địa chỉ API công khai (cho OAuth redirect)", False),
    "PUBLIC_WEB_URL": ("server", "Địa chỉ giao diện", False),
    **{f"INET_API_KEY_{n}": (f"nick:{n.lower()}", "Khoá API iNET", True) for n in NICKS},
    **{f"CPANEL_USER_{n}": (f"nick:{n.lower()}", "User cPanel", True) for n in NICKS},
    **{f"CPANEL_TOKEN_{n}": (f"nick:{n.lower()}", "API token cPanel", True) for n in NICKS},
    **{f"CPANEL_ADDON_API_{n}": (f"nick:{n.lower()}", "API tạo addon domain: api2 (mặc định) hoặc uapi — xem docs/API-RESEARCH.md", False) for n in NICKS},
}
SET_ONLY_BY_SERVER = {"GOOGLE_TOKEN"}
DEFAULTS = {**{f"CPANEL_ADDON_API_{n}": "api2" for n in NICKS}, "SHEET_TAB": "Phoi US", "SHEET_FIRST_ROW": "3", "AI_MODEL": "claude-opus-5-5", "PUBLIC_API_URL": "http://localhost:8000", "PUBLIC_WEB_URL": "http://localhost:3210"}  # written by the OAuth callback, never typed in

_cache: dict[str, tuple[str | None, float]] = {}
_TTL = 3.0


def _fernet() -> Fernet:
    key = os.environ.get("QLBM_MASTER_KEY") or _read_env_file("QLBM_MASTER_KEY")
    if not key:
        path = settings().data_dir / "master.key"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(Fernet.generate_key())
        key = path.read_text().strip()
    return Fernet(key.encode() if isinstance(key, str) else key)


def _db_value(name: str) -> str | None:
    hit = _cache.get(name)
    if hit and hit[1] > time.time():
        return hit[0]
    from .db import session_scope

    try:
        with session_scope() as s:
            row = s.get(StoredSetting, name)
            val = None
            if row:
                val = _fernet().decrypt(row.value.encode()).decode() if row.secret else row.value
    except InvalidToken:
        val = None  # wrong master key → treated as not set (the settings page shows it)
    except Exception:  # database not ready (e.g. very first start) → fall back to env
        val = None
    _cache[name] = (val, time.time() + _TTL)
    return val


def get(name: str, default: str = "") -> str:
    """Value for the integrations: the owner's setting first, then env / .env, then default."""
    v = _db_value(name)
    if v:
        return v
    return os.environ.get(name) or _read_env_file(name) or default


def source(name: str) -> str:
    if _db_value(name):
        return "app"
    if os.environ.get(name) or _read_env_file(name):
        return "env"
    return "none"


def put(name: str, value: str):
    from .db import session_scope

    if name not in FIELDS:
        raise KeyError(name)
    secret = FIELDS[name][2]
    with session_scope() as s:
        row = s.get(StoredSetting, name)
        if not value.strip():
            if row:
                s.delete(row)
        else:
            stored = _fernet().encrypt(value.strip().encode()).decode() if secret else value.strip()
            s.merge(StoredSetting(name=name, value=stored, secret=secret, updated_at=datetime.now(timezone.utc)))
    _cache.pop(name, None)


def describe() -> list[dict]:
    """For the settings page: which fields are set and from where — secret values are never included."""
    from .db import session_scope

    with session_scope() as s:
        rows = {r.name: r for r in s.query(StoredSetting)}
    out = []
    for name, (group, label, secret) in FIELDS.items():
        src = source(name)
        item = {"name": name, "group": group, "label": label, "secret": secret, "set": src != "none", "source": src,
                "updated_at": rows[name].updated_at.isoformat() if name in rows else None, "server_only": name in SET_ONLY_BY_SERVER}
        if not secret:
            item["value"] = get(name)
            item["default"] = DEFAULTS.get(name, "")
        out.append(item)
    return out
