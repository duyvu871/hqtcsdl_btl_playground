"""Tin crypto qua Alpha Vantage NEWS_SENTIMENT."""

from __future__ import annotations

import json
import ssl
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from lib.config import alpha_vantage_api_key
from lib.events import news_av_to_raw_event

if TYPE_CHECKING:
    from lib.progress import Progress

BASE_URL = "https://www.alphavantage.co/query"


def _fetch(params: dict[str, Any]) -> dict[str, Any]:
    full = {**params, "apikey": alpha_vantage_api_key()}
    url = f"{BASE_URL}?{urllib.parse.urlencode(full)}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "crypto-ingest-playground/0.1",
            "Accept": "application/json",
        },
        method="GET",
    )
    ctx = ssl.create_default_context()

    try:
        with urllib.request.urlopen(req, timeout=90, context=ctx) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Alpha Vantage HTTP {e.code}: {err}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Alpha Vantage request failed: {e.reason}") from e

    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError("Alpha Vantage trả về JSON không hợp lệ")
    if data.get("Note") or data.get("Information"):
        msg = data.get("Note") or data.get("Information")
        raise RuntimeError(f"Alpha Vantage: {msg}")
    return data


def collect_news_av_events(
    *,
    tickers: str = "CRYPTO:BTC,CRYPTO:ETH",
    days: int = 7,
    limit: int = 20,
    topics: str | None = None,
    progress: Progress | None = None,
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
    if topics:
        params["topics"] = topics

    if progress:
        progress.log(f"Alpha Vantage: đang gọi NEWS_SENTIMENT ({tickers})...")

    payload = _fetch(params)
    feed = payload.get("feed") or []
    if not isinstance(feed, list):
        if progress:
            progress.log("Alpha Vantage: feed rỗng hoặc không hợp lệ.")
        return []

    seen_urls: set[str] = set()
    events: list[dict[str, Any]] = []
    total = len(feed)
    if progress:
        progress.log(f"Alpha Vantage: xử lý {total} bài...")

    for i, article in enumerate(feed, start=1):
        if not isinstance(article, dict):
            continue
        url = str(article.get("url") or "").strip()
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        events.append(news_av_to_raw_event(article))
        if progress:
            progress.bar(i, total, prefix="Alpha Vantage: ")

    if progress:
        progress.log(f"Alpha Vantage: {len(events)} event(s) sau dedup URL.")

    return events
