"""Configuration the owner sets from the “Cài đặt API” page, stored server-side.

- Secrets (API keys, tokens, OAuth client/refresh token) are encrypted with Fernet before they reach PostgreSQL.
  The encryption key is QLBM_MASTER_KEY (env) or, if unset, data/master.key created on first use — it is never in the
  database, never in Git, and excluded from data backups: keep a copy in a password manager.
- Values set here win over the environment / .env (which keeps working as before).
- Nothing here ever returns a secret to the API layer except get() for the integrations themselves.
"""
import os
import re
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
    "SITE_COPY_AI": ("ai", "Viết nội dung website bằng AI: off (mặc định, miễn phí, viết sẵn theo ngành) hoặc on (cần khoá Anthropic, tốn phí)", False),
    "PEXELS_API_KEY": ("photos", "Khoá API Pexels", True),
    "PIXABAY_API_KEY": ("photos", "Khoá API Pixabay", True),
    "TWILIO_ACCOUNT_SID": ("phone", "Twilio Account SID (AC…)", True),
    "TWILIO_AUTH_TOKEN": ("phone", "Twilio Auth Token", True),
    "DOMAIN_START_ROW": ("server", "Tạo miền (B1) chỉ xét từ dòng này trở xuống — các dòng cũ phía trên bỏ qua dù cột B trống (trống = mọi dòng)", False),
    "DOMAIN_SKIP_ROWS": ("server", "Tạo miền (B1) bỏ qua các khối dòng này, vd 2762-2864 (nhiều khối cách nhau dấu phẩy)", False),
    "AUTO_SAVE_TO_SHEET": ("server", "Tự ghi Google Sheet khi đọc xong phôi OK / không có ô địa chỉ: true (mặc định) hoặc false", False),
    "MANUAL_REVIEW_MODE": ("server", "Duyệt từng file trước khi ghi Sheet: false (mặc định) hoặc true", False),
    "OCR_PERFORMANCE_MODE": ("server", "Chế độ OCR: NORMAL (mặc định — 1 việc OCR, máy vẫn dùng bình thường) hoặc FAST (2 việc cùng lúc, máy ≥ 8 luồng CPU; khởi động lại worker)", False),
    "PDF_INBOX_DIR": ("server", "Thư mục phôi: thả PDF vào là app nhận vào app rồi xoá hẳn file ngay (app giữ bản sao để đọc, duyệt, lên Drive) (mặc định Desktop\\Ảnh Phôi; off = tắt)", False),
    "OCR_CACHE_LIMIT_MB": ("server", "Giới hạn cache OCR (MB, mặc định 500) — chỉ lưu chữ + vị trí chữ đọc được, không lưu ảnh", False),
    "PUBLIC_API_URL": ("server", "Địa chỉ API công khai (cho OAuth redirect)", False),
    "PUBLIC_WEB_URL": ("server", "Địa chỉ giao diện", False),
    **{f"INET_API_KEY_{n}": (f"nick:{n.lower()}", "Khoá API iNET", True) for n in NICKS},
    **{f"CPANEL_USER_{n}": (f"nick:{n.lower()}", "User cPanel", True) for n in NICKS},
    **{f"CPANEL_TOKEN_{n}": (f"nick:{n.lower()}", "API token cPanel", True) for n in NICKS},
    **{f"CPANEL_ADDON_API_{n}": (f"nick:{n.lower()}", "API tạo addon domain: auto (mặc định: cPanel ≥ 138 dùng UAPI, thấp hơn dùng API 2), uapi hoặc api2", False) for n in NICKS},
}
SET_ONLY_BY_SERVER = {"GOOGLE_TOKEN"}


def credential_problem(name: str, value: str) -> str | None:
    """Why `value` cannot be this credential (None = plausible). Catches a wrong paste — a sentence, the page text, a
    key of another service — before it is stored. Never echoes the value."""
    v = value.strip()
    if not v:
        return None
    if name == "DOMAIN_SKIP_ROWS" and not re.fullmatch(r"\d+(-\d+)?(,\s*\d+(-\d+)?)*", v):
        return "Nhập khối dòng dạng 2762-2864 (nhiều khối cách nhau dấu phẩy)"
    if name == "DOMAIN_START_ROW" and not (v.isdigit() and int(v) >= 1):
        return "Nhập số dòng (vd 720)"
    if name in ("AUTO_SAVE_TO_SHEET", "MANUAL_REVIEW_MODE") and v.lower() not in ("true", "false"):
        return "Chỉ nhận true hoặc false"
    if name == "OCR_PERFORMANCE_MODE" and v.upper() not in ("NORMAL", "FAST"):
        return "Chế độ OCR chỉ nhận NORMAL hoặc FAST"
    if name.startswith("INET_API_KEY_"):
        # developers.inet.vn keys: "inet_sk_…" (Authorization: Bearer inet_sk_... in the official examples)
        if not v.startswith("inet_sk_") or not v.isascii() or any(c.isspace() for c in v):
            return "Khoá API iNET có dạng inet_sk_… (một chuỗi liền, không dấu, không khoảng trắng) — có vẻ đã dán nhầm nội dung khác"
    if name.startswith("CPANEL_TOKEN_"):
        if not v.isascii() or any(c.isspace() for c in v) or not (20 <= len(v) <= 64) or not v.isalnum():
            return "Token cPanel là một chuỗi chữ và số liền (khoảng 32 ký tự) — có vẻ đã dán nhầm nội dung khác"
    if name == "ANTHROPIC_API_KEY":
        if not v.startswith("sk-ant-") or not v.isascii() or any(c.isspace() for c in v):
            return "Khoá Anthropic có dạng sk-ant-… (một chuỗi liền) — có vẻ đã dán nhầm nội dung khác"
    if name == "TWILIO_ACCOUNT_SID" and not (v.startswith("AC") and len(v) == 34 and v.isalnum()):
        return "Twilio Account SID có dạng AC + 32 ký tự (một chuỗi liền) — có vẻ đã dán nhầm nội dung khác"
    if name == "TWILIO_AUTH_TOKEN" and not (len(v) == 32 and v.isalnum()):
        return "Twilio Auth Token là chuỗi 32 ký tự chữ và số — có vẻ đã dán nhầm nội dung khác"
    if name.startswith("CPANEL_USER_"):
        if not v.isascii() or any(c.isspace() for c in v) or len(v) > 64:
            return "User cPanel là một chuỗi liền, không dấu, không khoảng trắng"
    return None


def unusable_in_header(value: str) -> bool:
    """A stored credential that cannot even be sent (an HTTP header must be ASCII without spaces inside)."""
    return not value.isascii() or any(c.isspace() for c in value.strip())
DEFAULTS = {**{f"CPANEL_ADDON_API_{n}": "auto" for n in NICKS}, "SITE_COPY_AI": "off", "SHEET_TAB": "Phoi US", "SHEET_FIRST_ROW": "3", "AI_MODEL": "claude-opus-5-5", "PUBLIC_API_URL": "http://localhost:8000", "PUBLIC_WEB_URL": "http://localhost:3210"}  # written by the OAuth callback, never typed in

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


OFFLINE = False  # the PDF batch tool: settings from env / .env only — it never starts the database to read one


def _db_value(name: str) -> str | None:
    if OFFLINE:
        return None
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
