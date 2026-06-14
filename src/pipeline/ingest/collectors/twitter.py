"""Twitter/X collector — RapidAPI twitter154.

API key: RAPIDAPI_KEY trong .env
Dedup: theo tweet_id trong batch + unique index (source, external_id) ở MongoDB.
"""

from __future__ import annotations

import json
import logging
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Any

from src.common.config import settings
from src.pipeline.ingest.events import tweet_to_raw_event

logger = logging.getLogger(__name__)

BASE_URL = "https://twitter154.p.rapidapi.com/search/search"

DEFAULT_QUERY = (
    # Query mặc định: crypto macro + breaking news keywords
    "(bitcoin OR BTC OR ethereum OR ETH OR cryptocurrency OR crypto) "
    "(ETF OR Nasdaq OR market OR CPI OR inflation OR Fed OR treasury OR regulation OR macro OR reserve OR halving OR "
    "breaking OR merger OR subpoena OR outage OR roadmap OR bankrupt OR futures OR staking OR Layer2 OR scaling OR quarterly)"
)


def fetch_page(
    *,
    query: str,
    limit: int,
    min_likes: int,
    min_retweets: int,
    start_date: str | None,
    continuation_token: str | None = None,
) -> dict[str, Any]:
    params: dict[str, Any] = {
        "query": query,
        "section": "top",
        "min_retweets": min_retweets,
        "min_likes": min_likes,
        "limit": limit,
    }
    if start_date:
        params["start_date"] = start_date
    if continuation_token:
        params["continuation_token"] = continuation_token

    url = f"{BASE_URL}?{urllib.parse.urlencode(params)}"
    req = urllib.request.Request(
        url,
        headers={
            "X-RapidAPI-Key": settings.RAPIDAPI_KEY,
            "X-RapidAPI-Host": "twitter154.p.rapidapi.com",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Twitter HTTP {e.code}: {e.reason}\n{err[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Twitter request failed: {e.reason}") from e

    return json.loads(body)


def collect_twitter_events(
    *,
    query: str = DEFAULT_QUERY,
    max_pages: int = 1,
    limit_per_page: int = 10,
    min_likes: int = 50,
    min_retweets: int = 10,
    recency_days: int = 14,
) -> list[dict[str, Any]]:
    """Thu thập tweet → list raw_events. Raise nếu API lỗi."""
    start_date = (datetime.now(timezone.utc).date() - timedelta(days=recency_days)).isoformat()
    lim = max(1, min(20, limit_per_page))
    pages = max(1, max_pages)

    seen_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    token: str | None = None

    for _page in range(1, pages + 1):
        payload = fetch_page(
            query=query,
            limit=lim,
            min_likes=min_likes,
            min_retweets=min_retweets,
            start_date=start_date,
            continuation_token=token,
        )
        batch = payload.get("results") or []
        if not isinstance(batch, list):
            break

        for tweet in batch:
            if not isinstance(tweet, dict):
                continue
            tid = tweet.get("tweet_id")
            if tid is not None:
                key = str(tid)
                if key in seen_ids:
                    continue
                seen_ids.add(key)
            events.append(tweet_to_raw_event(tweet))

        token = payload.get("continuation_token")
        if not token or not str(token).strip():
            break

    logger.info("Twitter: collected %d events", len(events))
    return events
