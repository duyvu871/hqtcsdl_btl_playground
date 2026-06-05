"""Đọc biến môi trường — ưu tiên playground/ingest/.env (chung MongoDB)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_FILTER_DIR = Path(__file__).resolve().parent.parent
_INGEST_ENV = _FILTER_DIR.parent / "ingest" / ".env"

load_dotenv(_INGEST_ENV)
load_dotenv(_FILTER_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Điền trong playground/ingest/.env hoặc playground/filter/.env."
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


def dropped_collection() -> str:
    return (
        os.getenv("MONGODB_DROPPED_COLLECTION", "dropped_events").strip()
        or "dropped_events"
    )


def fasttext_model_path() -> Path:
    raw = os.getenv("FASTTEXT_MODEL_PATH", "").strip()
    if raw:
        return Path(raw).expanduser()
    return (
        _FILTER_DIR.parent / "finetune" / "fasttext" / "models" / "spam_model.bin"
    )
