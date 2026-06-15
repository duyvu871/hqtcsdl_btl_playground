"""Yahoo Finance news collector — yfinance.

Không cần API key. Cần: uv sync --extra pipeline
Dedup: external_id trong batch.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from src.pipeline.ingest.events import news_yahoo_to_raw_event

logger = logging.getLogger(__name__)

_YF_CACHE = Path(__file__).resolve().parents[4] / ".cache" / "yfinance"


def _load_yfinance():
    """Import yfinance — optional dep (dev group hoặc --extra pipeline)."""
    try:
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "Thiếu yfinance — cài: uv sync hoặc uv sync --extra pipeline"
        ) from e
    return yf


def _ensure_yfinance_cache() -> None:
    _YF_CACHE.mkdir(parents=True, exist_ok=True)
    yf = _load_yfinance()
    yf.set_tz_cache_location(str(_YF_CACHE))


def collect_news_yahoo_events(
    *,
    symbol: str = "BTC-USD",
    limit: int = 20,
) -> list[dict[str, Any]]:
    _ensure_yfinance_cache()
    yf = _load_yfinance()

    ticker = yf.Ticker(symbol)
    raw_news = getattr(ticker, "news", None) or []
    if not isinstance(raw_news, list):
        return []

    seen_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    for article in raw_news[: max(1, limit)]:
        if not isinstance(article, dict):
            continue
        event = news_yahoo_to_raw_event(article, symbol=symbol)
        if event is None:
            continue
        ext_id = str(event.get("external_id") or "")
        if ext_id and ext_id in seen_ids:
            continue
        if ext_id:
            seen_ids.add(ext_id)
        events.append(event)

    logger.info("Yahoo Finance: collected %d events for %s", len(events), symbol)
    return events
