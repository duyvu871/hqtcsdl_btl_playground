"""Map mapped_event + score → sentiment_events document (L-01 metadata)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any


def normalize_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, str):
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (ValueError, TypeError):
            pass
        try:
            return int(float(value))
        except (ValueError, TypeError):
            pass
    return None


def build_sentiment_event(
    mapped_event: dict[str, Any],
    sentiment_result: dict[str, Any],
) -> dict[str, Any]:
    """Tạo sentiment_event — propagate filter_meta + ner_meta (L-01)."""
    doc: dict[str, Any] = {
        "sentiment_id": str(uuid.uuid4()),
        "mapped_id": mapped_event.get("mapped_id"),
        "event_id": mapped_event.get("event_id"),
        "parent_event_id": mapped_event.get("parent_event_id"),
        "coin_id": mapped_event["coin_id"],
        "source": mapped_event.get("source"),
        "clean_text": mapped_event.get("clean_text") or mapped_event.get("raw_text", ""),
        "author_id": mapped_event.get("author_id"),
        "metrics": mapped_event.get("metrics") or {},
        "timestamp": normalize_timestamp(mapped_event.get("timestamp")),
        "sentiment_score": sentiment_result["sentiment_score"],
        "sentiment_label": sentiment_result["sentiment_label"],
        "sentiment_confidence": sentiment_result.get("sentiment_confidence"),
        "probabilities": sentiment_result.get("probabilities", {}),
        "method": sentiment_result.get("method", "rule_based"),
        "sentiment_model": sentiment_result.get("sentiment_model"),
        "filter_meta": mapped_event.get("filter") or {},
        "ner_meta": mapped_event.get("ner") or {},
        "scored_at": datetime.now(timezone.utc),
    }
    for key in (
        "external_id",
        "tweet_id",
        "language",
        "news_provider",
        "related_tickers",
        "subreddit",
        "extra",
    ):
        if key in mapped_event:
            doc[key] = mapped_event[key]
    return doc
