"""Đọc biến môi trường — ưu tiên playground/ingest/.env (chung MongoDB)."""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_SCORING_DIR = Path(__file__).resolve().parent.parent
_INGEST_ENV = _SCORING_DIR.parent / "ingest" / ".env"

load_dotenv(_INGEST_ENV)
load_dotenv(_SCORING_DIR / ".env")


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Điền trong playground/ingest/.env hoặc playground/scoring/.env."
        )
    return value


def mongodb_uri() -> str:
    return _require("MONGODB_URI")


def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip() or "crypto_mvp"


def aggregate_collection() -> str:
    """Bảng nguồn: Chứa dữ liệu tâm lý đã tổng hợp từ Bước 4."""
    return (
        os.getenv("MONGODB_AGGREGATE_COLLECTION", "sentiment_aggregates").strip()
        or "sentiment_aggregates"
    )


def signal_collection() -> str:
    """Bảng đích: Chứa kết quả JSON Payload (Tín hiệu mua/bán) của Bước 6."""
    return (
        os.getenv("MONGODB_SIGNAL_COLLECTION", "scoring_signals").strip()
        or "scoring_signals"
    )