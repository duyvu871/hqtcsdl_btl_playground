"""Alpha Vantage NEWS_SENTIMENT collector.

API key: ALPHA_VANTAGE_API_KEY
Rate limit: free tier 25 req/day — dùng limit nhỏ khi test.
"""

from __future__ import annotations

import json
import logging
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from src.common.config import settings
from src.pipeline.ingest.events import news_av_to_raw_event

logger = logging.getLogger(__name__)

BASE_URL = "https://www.alphavantage.co/query"


def _fetch(params: dict[str, Any]) -> dict[str, Any]:
    full = {**params, "apikey": settings.ALPHA_VANTAGE_API_KEY}
    url = f"{BASE_URL}?{urllib.parse.urlencode(full)}"
    req = urllib.request.Request(
        url,
        headers={"User-Agent": "crypto-pipeline/0.1", "Accept": "application/json"},
        method="GET",
    )
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Alpha Vantage HTTP {e.code}: {err[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Alpha Vantage request failed: {e.reason}") from e

    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError("Alpha Vantage: invalid JSON")
    if data.get("Note") or data.get("Information"):
        raise RuntimeError(f"Alpha Vantage: {data.get('Note') or data.get('Information')}")
    return data


def collect_news_av_events(
    *,
    tickers: str = "CRYPTO:BTC,CRYPTO:ETH",
    days: int = 7,
    limit: int = 20,
) -> list[dict[str, Any]]:
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=max(1, days))
    params: dict[str, Any] = {
        "function": "NEWS_SENTIMENT",
        "tickers": tickers,
        "time_from": start.strftime("%Y%m%dT%H%M"),
        "time_to": now.strftime("%Y%m%dT%H%M"),
        "limit": str(max(1, min(1000, limit))),
        "sort": "RELEVANCE",
    }

    payload = _fetch(params)
    feed = payload.get("feed") or []
    if not isinstance(feed, list):
        return []

    seen_urls: set[str] = set()
    events: list[dict[str, Any]] = []
    for article in feed:
        if not isinstance(article, dict):
            continue
        url = str(article.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        events.append(news_av_to_raw_event(article))

    logger.info("Alpha Vantage: collected %d events", len(events))
    return events
