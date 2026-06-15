"""Map sentiment_event → weighted_event + scoring trigger payload."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.common.config import settings
from src.pipeline.influence.scoring import calculate_influence, normalize_timestamp, to_float


def source_event_key(event: dict[str, Any]) -> str:
    for key in ("sentiment_id", "mapped_id"):
        value = event.get(key)
        if value:
            return str(value)

    event_id = event.get("event_id") or event.get("parent_event_id") or "unknown_event"
    coin_id = event.get("coin_id") or "unknown_coin"
    return f"{event_id}:{coin_id}"


def build_weighted_event(
    sentiment_event: dict[str, Any],
    *,
    reference_ts: int | None = None,
) -> dict[str, Any]:
    """Tạo weighted_event từ sentiment_event."""
    influence = calculate_influence(sentiment_event, reference_ts=reference_ts)
    sentiment_score = to_float(sentiment_event.get("sentiment_score"), 0.0)
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
        "ner_meta",
        "filter",
        "filter_meta",
        "extra",
    ):
        if key in sentiment_event:
            doc[key] = sentiment_event[key]

    return doc


def aggregate_to_social_row(agg: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa influence_aggregate → row join scoring."""
    ws = agg.get("window_start")
    if isinstance(ws, datetime):
        ts = int(ws.timestamp())
    else:
        ts = int(ws) if ws is not None else 0

    return {
        "timestamp": float(ts),
        "coin_id": agg.get("coin_id"),
        "sentiment_score": agg.get("sentiment_score", agg.get("influence_weighted_sentiment", 0.0)),
        "social_volume": agg.get("social_volume", agg.get("event_count", 0)),
    }


def build_scoring_trigger(
    aggregate: dict[str, Any],
    social_history: list[dict[str, Any]],
) -> dict[str, Any]:
    """Batch-trigger payload cho Stage 6 — đủ context qua transport."""
    return {
        "coin_id": aggregate.get("coin_id"),
        "timeframe": aggregate.get("timeframe", settings.INFLUENCE_TIMEFRAME),
        "aggregate": aggregate,
        "social_history": social_history,
        "triggered_at": datetime.now(timezone.utc).isoformat(),
    }
