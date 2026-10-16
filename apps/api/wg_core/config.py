"""Settings from environment / .env (never committed). Secrets live only here or in the server's env."""
import os
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

API_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = API_ROOT / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=ENV_FILE, env_file_encoding="utf-8", extra="ignore")

    database_url: str = ""  # empty → local embedded PostgreSQL (dev only, see wg_core/devdb.py)
    data_dir: Path = API_ROOT / "data"  # uploaded PDFs, built sites, backups (gitignored)
    cors_origins: str = "http://localhost:3000,http://localhost:3210"

    # Google (service account; the Sheet and the Drive folder must be shared with its email)
    google_service_account_file: str = ""
    sheet_id: str = ""
    sheet_tab: str = "Phoi US"
    drive_folder_id: str = ""

    # AI — Anthropic is the main provider. Model default per current Anthropic guidance.
    anthropic_api_key: str = ""
    ai_model: str = "claude-opus-5-5"

    # Non-secret nick + root-domain data; default config/nicks.example.json
    nicks_file: str = ""

    worker_poll_seconds: float = 1.0


@lru_cache
def settings() -> Settings:
    return Settings()


def _read_env_file(name: str) -> str:
    if not ENV_FILE.exists():
        return ""
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        k, sep, v = line.partition("=")
        if sep and k.strip() == name:
            return v.strip().strip('"').strip("'")
    return ""


def env_secret(name: str) -> str:
    """Per-nick secret (INET_API_KEY_N1, CPANEL_USER_N1, CPANEL_TOKEN_N1…) from env or .env. Never logged."""
    return os.environ.get(name) or _read_env_file(name)
