"""Application configuration loaded from environment variables."""
import os
import sys
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


def data_dir() -> Path:
    """Where the exe keeps its DB and .env. Next to the exe, or cwd in dev."""
    if getattr(sys, "frozen", False):
        base = Path(sys.executable).resolve().parent
    else:
        base = Path.cwd()
    d = base / "sshpilot_data"
    d.mkdir(exist_ok=True)
    return d


_DATA = data_dir()
_ENV_FILE = _DATA / ".env"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=str(_ENV_FILE), extra="ignore")

    # Core
    app_name: str = "SSHPilot"
    debug: bool = False
    database_url: str = f"sqlite+aiosqlite:///{(_DATA / 'sshpilot.db').as_posix()}"

    # Security
    # SECRET_KEY signs JWTs. ENCRYPTION_KEY (base64 32 bytes) encrypts SSH creds.
    secret_key: str = "change-me-in-prod-please-use-a-long-random-string"
    encryption_key: str = ""  # if empty, derived from secret_key (dev only)
    access_token_expire_minutes: int = 60 * 24 * 7

    # LLM
    anthropic_api_key: str = ""
    agent_model: str = "claude-sonnet-4-20250514"
    agent_max_steps: int = 25

    # SSH
    ssh_connect_timeout: int = 15
    command_timeout: int = 120

    # CORS
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000", "http://localhost:8000"]


# ---- Runtime settings overlay (persisted JSON in the data dir) ----
# Lets a packaged-exe user set their Anthropic key from the UI without editing
# files. These override env values when present.
import json

_RUNTIME_FILE = _DATA / "runtime.json"


def load_runtime() -> dict:
    if _RUNTIME_FILE.is_file():
        try:
            return json.loads(_RUNTIME_FILE.read_text())
        except (json.JSONDecodeError, OSError):
            return {}
    return {}


def save_runtime(data: dict) -> None:
    current = load_runtime()
    current.update({k: v for k, v in data.items() if v is not None})
    _RUNTIME_FILE.write_text(json.dumps(current, indent=2))
    get_settings.cache_clear()


def ensure_encryption_key() -> None:
    """Generate a stable Fernet key on first run if none is configured."""
    rt = load_runtime()
    if not rt.get("encryption_key"):
        from cryptography.fernet import Fernet

        save_runtime({"encryption_key": Fernet.generate_key().decode()})


@lru_cache
def get_settings() -> "Settings":
    s = Settings()
    rt = load_runtime()
    if rt.get("anthropic_api_key"):
        s.anthropic_api_key = rt["anthropic_api_key"]
    if rt.get("encryption_key"):
        s.encryption_key = rt["encryption_key"]
    if rt.get("agent_model"):
        s.agent_model = rt["agent_model"]
    return s


def data_path() -> Path:
    return _DATA
