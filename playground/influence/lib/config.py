"""Đọc cấu hình cho Stage 5 — Influence Weighting.

Module này cố ý chỉ phụ thuộc vào folder `playground/influence` và file env chung
ở `playground/ingest/.env`. Không sửa hoặc import code từ stage khác.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

_INFLUENCE_DIR = Path(__file__).resolve().parent.parent
_PLAYGROUND_DIR = _INFLUENCE_DIR.parent
_INGEST_ENV = _PLAYGROUND_DIR / "ingest" / ".env"
_INFLUENCE_ENV = _INFLUENCE_DIR / ".env"

# Load env chung trước, env riêng influence sau để có thể override.
load_dotenv(_INGEST_ENV)
load_dotenv(_INFLUENCE_ENV)


def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(
            f"Thiếu {name}. Điền trong playground/ingest/.env hoặc playground/influence/.env."
        )
    return value


def _float_env(name: str, default: float) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        return float(raw)
    except ValueError:
        return default


def _int_env(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        return int(raw)
    except ValueError:
        return default


def mongodb_uri() -> str:
    return _require("MONGODB_URI")


def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip() or "crypto_mvp"


def sentiment_collection() -> str:
    return (
        os.getenv("MONGODB_SENTIMENT_COLLECTION", "sentiment_events").strip()
        or "sentiment_events"
    )


def weighted_collection() -> str:
    return (
        os.getenv("MONGODB_WEIGHTED_COLLECTION", "weighted_events").strip()
        or "weighted_events"
    )


def influence_agg_collection() -> str:
    return (
        os.getenv("MONGODB_INFLUENCE_AGG_COLLECTION", "influence_aggregates").strip()
        or "influence_aggregates"
    )


def max_influence() -> float:
    return _float_env("MAX_INFLUENCE", 20.0)


def core_scale() -> float:
    return _float_env("CORE_SCALE", 8.0)


def alpha_author() -> float:
    return _float_env("ALPHA_AUTHOR", 0.35)


def beta_engagement() -> float:
    return _float_env("BETA_ENGAGEMENT", 0.40)


def gamma_virality() -> float:
    return _float_env("GAMMA_VIRALITY", 0.25)


def delta_network() -> float:
    return _float_env("DELTA_NETWORK", 0.0)


def default_expected_engagement() -> float:
    return _float_env("DEFAULT_EXPECTED_ENGAGEMENT", 50.0)


def half_life_hours_for_source(source: str | None) -> float:
    source_key = (source or "").strip().lower()
    if source_key in {"twitter", "x"}:
        return _float_env("TWITTER_HALF_LIFE_HOURS", 12.0)
    if source_key == "reddit":
        return _float_env("REDDIT_HALF_LIFE_HOURS", 24.0)
    if source_key in {"news", "alpha_vantage", "yahoo_finance"}:
        return _float_env("NEWS_HALF_LIFE_HOURS", 36.0)
    return _float_env("DEFAULT_HALF_LIFE_HOURS", 24.0)
