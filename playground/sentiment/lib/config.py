"""Đọc biến môi trường — ưu tiên playground/ingest/.env (chung MongoDB)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_SENTIMENT_DIR = Path(__file__).resolve().parent.parent
_INGEST_ENV = _SENTIMENT_DIR.parent / "ingest" / ".env"

load_dotenv(_INGEST_ENV)
load_dotenv(_SENTIMENT_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Điền trong playground/ingest/.env hoặc playground/sentiment/.env."
        )
    return value


def mongodb_uri() -> str:
    return _require("MONGODB_URI")


def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip() or "crypto_mvp"


def mapped_collection() -> str:
    return (
        os.getenv("MONGODB_MAPPED_COLLECTION", "mapped_events").strip()
        or "mapped_events"
    )


def clean_collection() -> str:
    return (
        os.getenv("MONGODB_CLEAN_COLLECTION", "clean_events").strip()
        or "clean_events"
    )


def sentiment_collection() -> str:
    return (
        os.getenv("MONGODB_SENTIMENT_COLLECTION", "sentiment_events").strip()
        or "sentiment_events"
    )


def aggregate_collection() -> str:
    return (
        os.getenv("MONGODB_AGGREGATE_COLLECTION", "sentiment_aggregates").strip()
        or "sentiment_aggregates"
    )


def sentiment_model() -> str:
    return os.getenv("SENTIMENT_MODEL", "ProsusAI/finbert").strip() or "ProsusAI/finbert"


def sentiment_batch_size() -> int:
    raw = os.getenv("SENTIMENT_BATCH_SIZE", "100").strip()
    try:
        return int(raw)
    except ValueError:
        return 100


def sentiment_max_length() -> int:
    raw = os.getenv("SENTIMENT_MAX_LENGTH", "256").strip()
    try:
        return int(raw)
    except ValueError:
        return 256


def use_rule_fallback() -> bool:
    raw = os.getenv("SENTIMENT_USE_RULE_FALLBACK", "true").strip().lower()
    return raw in ("true", "1", "yes")
