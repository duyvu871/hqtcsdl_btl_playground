"""Tin gắn mã crypto qua yfinance (Yahoo Finance)."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any

from lib.events import news_yahoo_to_raw_event

if TYPE_CHECKING:
    from lib.progress import Progress

_YF_CACHE = Path(__file__).resolve().parent.parent.parent / ".cache" / "yfinance"


def _ensure_yfinance_cache() -> None:
    _YF_CACHE.mkdir(parents=True, exist_ok=True)
    import yfinance as yf

    yf.set_tz_cache_location(str(_YF_CACHE))


def collect_news_yahoo_events(
    *,
    symbol: str = "BTC-USD",
    limit: int = 20,
    progress: Progress | None = None,
) -> list[dict[str, Any]]:
    try:
        _ensure_yfinance_cache()
        import yfinance as yf
    except ImportError as e:
        raise RuntimeError(
            "Thiếu yfinance. Chạy: uv sync (trong playground/ingest)"
        ) from e

    if progress:
        progress.log(f"Yahoo Finance: đang tải tin cho {symbol}...")

    ticker = yf.Ticker(symbol)
    raw_news = getattr(ticker, "news", None) or []
    if not isinstance(raw_news, list):
        if progress:
            progress.log("Yahoo Finance: không có tin.")
        return []

    articles = raw_news[: max(1, limit)]
    seen_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    skipped_empty = 0
    total = len(articles)
    if progress:
        progress.log(f"Yahoo Finance: xử lý {total} bài...")

    for i, article in enumerate(articles, start=1):
        if not isinstance(article, dict):
            skipped_empty += 1
            continue

        event = news_yahoo_to_raw_event(article, symbol=symbol)
        if event is None:
            skipped_empty += 1
            continue

        ext_id = str(event.get("external_id") or "")
        if ext_id and ext_id in seen_ids:
            continue
        if ext_id:
            seen_ids.add(ext_id)
        events.append(event)
        if progress:
            progress.bar(i, total, prefix="Yahoo Finance: ")

    if progress:
        msg = f"Yahoo Finance: {len(events)} event(s)."
        if skipped_empty:
            msg += f" Bỏ qua {skipped_empty} bài không có nội dung."
        progress.log(msg)

    return events
