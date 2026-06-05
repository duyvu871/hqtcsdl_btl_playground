"""Đọc biến môi trường từ file .env (cùng thư mục playground/ingest)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_FILE)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Sao chép .env.example → .env và điền giá trị."
        )
    return value


def _optional(name: str) -> str | None:
    value = os.getenv(name, "").strip()
    return value or None


def rapidapi_key() -> str:
    return _require("RAPIDAPI_KEY")


def alpha_vantage_api_key() -> str:
    return _require("ALPHA_VANTAGE_API_KEY")


def mongodb_uri() -> str:
    return _require("MONGODB_URI")


def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip() or "crypto_mvp"


def mongodb_collection() -> str:
    return os.getenv("MONGODB_COLLECTION", "raw_events").strip() or "raw_events"


def reddit_user_agent() -> str:
    return (
        os.getenv("REDDIT_USER_AGENT", "").strip()
        or "linux:crypto-ingest-playground:v0.1 (by /u/adc300)"
    )


def reddit_client_id() -> str | None:
    return _optional("REDDIT_CLIENT_ID")


def reddit_client_secret() -> str | None:
    return _optional("REDDIT_CLIENT_SECRET")


def reddit_username() -> str | None:
    return _optional("REDDIT_USERNAME")


def reddit_password() -> str | None:
    return _optional("REDDIT_PASSWORD")


def reddit_oauth_configured() -> bool:
    return bool(reddit_client_id() and reddit_username() and reddit_password())


def reddit_browser_headless() -> bool:
    return os.getenv("REDDIT_BROWSER_HEADLESS", "true").strip().lower() not in (
        "0",
        "false",
        "no",
    )


def reddit_browser_storage_path() -> Path:
    raw = os.getenv("REDDIT_BROWSER_STORAGE", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _ENV_FILE.parent / ".reddit_session.json"
