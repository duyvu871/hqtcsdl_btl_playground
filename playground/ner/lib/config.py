"""Đọc biến môi trường — ưu tiên playground/ingest/.env (chung MongoDB)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_NER_DIR = Path(__file__).resolve().parent.parent
_INGEST_ENV = _NER_DIR.parent / "ingest" / ".env"

load_dotenv(_INGEST_ENV)
load_dotenv(_NER_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Điền trong playground/ingest/.env hoặc playground/ner/.env."
        )
    return value


def mongodb_uri() -> str:
    return _require("MONGODB_URI")


def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip() or "crypto_mvp"


def raw_collection() -> str:
    return os.getenv("MONGODB_COLLECTION", "raw_events").strip() or "raw_events"


def clean_collection() -> str:
    return (
        os.getenv("MONGODB_CLEAN_COLLECTION", "clean_events").strip()
        or "clean_events"
    )


def mapped_collection() -> str:
    return (
        os.getenv("MONGODB_MAPPED_COLLECTION", "mapped_events").strip()
        or "mapped_events"
    )


def openrouter_api_key() -> str:
    return _require("OPENROUTER_API_KEY")


def openrouter_model() -> str:
    return _require("OPENROUTER_MODEL")


def openrouter_base_url() -> str:
    return (
        os.getenv("OPENROUTER_BASE_URL", "https://openrouter.ai/api/v1").strip()
        or "https://openrouter.ai/api/v1"
    )


def openrouter_site_url() -> str | None:
    value = os.getenv("OPENROUTER_SITE_URL", "").strip()
    return value or None


def openrouter_app_name() -> str:
    return os.getenv("OPENROUTER_APP_NAME", "crypto-ner-playground").strip()


def ner_mode_default() -> str:
    return os.getenv("NER_MODE", "hybrid").strip().lower() or "hybrid"


def coin_registry_path() -> Path:
    raw = os.getenv("COIN_REGISTRY_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return _NER_DIR / "data" / "coin_registry.json"
