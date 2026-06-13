"""Schema builder cho Stage 5.

- Input: sentiment_events từ Stage 4.
- Output 1: weighted_events — từng event đã có influence_weight.
- Output 2: influence_aggregates — dữ liệu social theo coin/timeframe cho Stage 6.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from lib.scoring import calculate_influence, normalize_timestamp, to_float


def source_event_key(event: dict[str, Any]) -> str:
    """Tạo key ổn định để chống insert trùng.

    Ưu tiên sentiment_id vì đây là output duy nhất của Stage 4. Nếu không có thì
    fallback sang mapped_id/event_id + coin_id.
    """
    for key in ("sentiment_id", "mapped_id"):
        value = event.get(key)
        if value:
            return str(value)

    event_id = event.get("event_id") or event.get("parent_event_id") or "unknown_event"
    coin_id = event.get("coin_id") or "unknown_coin"
    return f"{event_id}:{coin_id}"


def _sentiment_score(event: dict[str, Any]) -> float:
    return to_float(event.get("sentiment_score"), 0.0)


def build_weighted_event(
    sentiment_event: dict[str, Any],
    *,
    reference_ts: int | None = None,
) -> dict[str, Any]:
    """Tạo weighted_event từ sentiment_event."""
    influence = calculate_influence(sentiment_event, reference_ts=reference_ts)
    sentiment_score = _sentiment_score(sentiment_event)
    influence_weight = influence["influence_weight"]
    weighted_sentiment = sentiment_score * influence_weight

    timestamp = normalize_timestamp(sentiment_event.get("timestamp"))

    doc: dict[str, Any] = {
        "weighted_id": str(uuid.uuid4()),
        "source_event_key": source_event_key(sentiment_event),
        "sentiment_id": sentiment_event.get("sentiment_id"),
        "mapped_id": sentiment_event.get("mapped_id"),
        "event_id": sentiment_event.get("event_id"),
        "parent_event_id": sentiment_event.get("parent_event_id"),
        "coin_id": sentiment_event.get("coin_id"),
        "source": sentiment_event.get("source"),
        "author_id": sentiment_event.get("author_id"),
        "clean_text": sentiment_event.get("clean_text") or sentiment_event.get("raw_text", ""),
        "metrics": sentiment_event.get("metrics") or {},
        "timestamp": timestamp,
        "sentiment_score": sentiment_score,
        "sentiment_label": sentiment_event.get("sentiment_label"),
        "sentiment_confidence": sentiment_event.get("sentiment_confidence"),
        "influence_weight": influence_weight,
        "weighted_sentiment": round(weighted_sentiment, 6),
        "influence": influence,
        "weighted_at": datetime.now(timezone.utc),
    }

    # Giữ lại metadata quan trọng nếu Stage 4 có truyền sang.
    for key in (
        "external_id",
        "tweet_id",
        "language",
        "news_provider",
        "related_tickers",
        "subreddit",
        "probabilities",
        "sentiment_model",
        "ner",
        "filter",
        "filter_meta",
        "extra",
    ):
        if key in sentiment_event:
            doc[key] = sentiment_event[key]

    return doc


def utc_dt_from_ts(ts: int) -> datetime:
    return datetime.fromtimestamp(ts, tz=timezone.utc)
