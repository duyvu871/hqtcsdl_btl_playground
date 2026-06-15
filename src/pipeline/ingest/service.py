"""Stage 1 business logic — dispatch collectors theo kickoff payload.

Luồng:
  Orchestrator XADD stage:ingest:in {coin_id, sources[]}
    → ingest_processor() gọi collect_from_kickoff()
    → mỗi source trong SOURCE_REGISTRY
    → trả list raw_events
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from typing import Any

from src.common.config import settings
from src.pipeline.ingest.collectors import (
    collect_news_av_events,
    collect_news_yahoo_events,
    collect_reddit_events,
    collect_twitter_events,
)

logger = logging.getLogger(__name__)

# kickoff sources[] → collector function
CollectorFn = Callable[..., list[dict[str, Any]]]

# Registry: tên kickoff → (hàm collector, kwargs mặc định)
SOURCE_REGISTRY: dict[str, tuple[CollectorFn, dict[str, Any]]] = {
    "twitter": (
        collect_twitter_events,
        {"max_pages": 1, "limit_per_page": 10},
    ),
    "news-av": (
        collect_news_av_events,
        {"limit": 20},
    ),
    "news-yahoo": (
        collect_news_yahoo_events,
        {"limit": 20},
    ),
    "reddit": (
        collect_reddit_events,
        {"limit": 25},
    ),
}


def _coin_to_yahoo_symbol(coin_id: str) -> str:
    """BTC → BTC-USD cho yfinance."""
    base = coin_id.upper().replace("CRYPTO:", "").strip()
    if "-" in base:
        return base
    return f"{base}-USD"


def _coin_to_av_tickers(coin_id: str) -> str:
    """BTC → CRYPTO:BTC cho Alpha Vantage tickers param."""
    base = coin_id.upper().replace("CRYPTO:", "").strip()
    return f"CRYPTO:{base}"


def _source_available(source: str) -> bool:
    """Kiểm tra API key trước khi gọi — graceful fallback."""
    if source == "twitter":
        return bool(settings.RAPIDAPI_KEY)
    if source == "news-av":
        return bool(settings.ALPHA_VANTAGE_API_KEY)
    if source == "news-yahoo":
        return True
    if source == "reddit":
        return bool(settings.REDDIT_CLIENT_ID and settings.REDDIT_USERNAME)
    return False


def collect_from_kickoff(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """
    Đọc kickoff entry: {coin_id, timeframe, sources[]}.
    Gọi từng collector; skip nguồn thiếu key hoặc lỗi.
    """
    coin_id = str(payload.get("coin_id") or "BTC")
    sources = payload.get("sources") or ["twitter"]
    if isinstance(sources, str):
        sources = [sources]

    all_events: list[dict[str, Any]] = []

    for source in sources:
        source = str(source).strip()
        if source not in SOURCE_REGISTRY:
            logger.warning("Unknown source '%s' — skip", source)
            continue

        if not _source_available(source):
            logger.warning("Source '%s' thiếu API key — skip", source)
            continue

        fn, defaults = SOURCE_REGISTRY[source]
        kwargs = dict(defaults)

        # Inject coin context cho news collectors
        if source == "news-yahoo":
            kwargs["symbol"] = _coin_to_yahoo_symbol(coin_id)
        elif source == "news-av":
            kwargs["tickers"] = _coin_to_av_tickers(coin_id)

        try:
            events = fn(**kwargs)
            all_events.extend(events)
            logger.info("Source %s: %d events", source, len(events))
        except Exception as exc:
            logger.warning("Source %s failed: %s — tiếp tục nguồn khác", source, exc)

    return all_events
