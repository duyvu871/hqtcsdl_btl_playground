"""Aggregate sentiment theo coin_id + timeframe."""

from __future__ import annotations

import logging
import math
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import aggregate_collection, sentiment_collection

logger = logging.getLogger(__name__)

# Timeframe → seconds
TIMEFRAME_SECONDS: dict[str, int] = {
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 3600,
    "4h": 4 * 3600,
    "1d": 86400,
}


def _compute_influence(metrics: dict[str, Any]) -> float:
    """Tính influence weight từ social metrics.
    
    Formula: 1 + log1p(followers) + 0.1 * likes + 0.3 * retweets + 0.2 * replies
    """
    followers = max(0, int(metrics.get("followers", 0) or 0))
    likes = max(0, int(metrics.get("likes", 0) or 0))
    retweets = max(0, int(metrics.get("retweets", 0) or 0))
    replies = max(0, int(metrics.get("replies", 0) or 0))

    return 1 + math.log1p(followers) + 0.1 * likes + 0.3 * retweets + 0.2 * replies


def _window_start(ts: int, interval_seconds: int) -> int:
    """Snap timestamp về đầu window."""
    return (ts // interval_seconds) * interval_seconds


def aggregate_sentiment(
    db,
    *,
    timeframe: str = "1h",
    coin_id: str | None = None,
    since_ts: int | None = None,
) -> int:
    """Aggregate sentiment_events → sentiment_aggregates.
    
    Returns:
        Số lượng aggregate documents upserted.
    """
    interval = TIMEFRAME_SECONDS.get(timeframe)
    if interval is None:
        raise ValueError(
            f"Timeframe '{timeframe}' không hợp lệ. "
            f"Chọn: {', '.join(TIMEFRAME_SECONDS.keys())}"
        )

    sent_col = db[sentiment_collection()]
    agg_col = db[aggregate_collection()]

    # Build query
    query: dict[str, Any] = {
        "timestamp": {"$exists": True, "$ne": None},
        "sentiment_score": {"$exists": True},
    }
    if coin_id:
        query["coin_id"] = coin_id
    if since_ts is not None:
        query["timestamp"] = {"$gte": since_ts}

    events = list(sent_col.find(query))
    if not events:
        logger.info("Không có sentiment_events để aggregate.")
        return 0

    logger.info("Aggregating %d sentiment_events (timeframe=%s)...", len(events), timeframe)

    # Group by (coin_id, window_start)
    buckets: dict[tuple[str, int], list[dict[str, Any]]] = {}
    for event in events:
        cid = event.get("coin_id")
        ts = event.get("timestamp")
        if not cid or ts is None:
            continue
        ws = _window_start(int(ts), interval)
        key = (cid, ws)
        buckets.setdefault(key, []).append(event)

    upserted = 0
    for (cid, ws), bucket_events in buckets.items():
        scores = [e["sentiment_score"] for e in bucket_events]
        labels = [e.get("sentiment_label", "neutral") for e in bucket_events]

        # Weighted sentiment
        weighted_sum = 0.0
        weight_total = 0.0
        for e in bucket_events:
            influence = _compute_influence(e.get("metrics") or {})
            weighted_sum += e["sentiment_score"] * influence
            weight_total += influence

        avg_sentiment = sum(scores) / len(scores) if scores else 0.0
        weighted_sentiment = weighted_sum / weight_total if weight_total > 0 else 0.0

        window_start_dt = datetime.fromtimestamp(ws, tz=timezone.utc)
        window_end_dt = datetime.fromtimestamp(ws + interval, tz=timezone.utc)

        agg_doc: dict[str, Any] = {
            "coin_id": cid,
            "timeframe": timeframe,
            "window_start": window_start_dt,
            "window_end": window_end_dt,
            "event_count": len(bucket_events),
            "avg_sentiment": round(avg_sentiment, 4),
            "weighted_sentiment": round(weighted_sentiment, 4),
            "positive_count": labels.count("positive"),
            "neutral_count": labels.count("neutral"),
            "negative_count": labels.count("negative"),
            "updated_at": datetime.now(timezone.utc),
        }

        # Upsert
        agg_col.update_one(
            {
                "coin_id": cid,
                "timeframe": timeframe,
                "window_start": window_start_dt,
            },
            {"$set": agg_doc},
            upsert=True,
        )
        upserted += 1

    logger.info("Upserted %d aggregate documents.", upserted)
    return upserted
