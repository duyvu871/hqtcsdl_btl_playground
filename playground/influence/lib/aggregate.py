from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from pymongo.collection import Collection

TIMEFRAME_SECONDS: dict[str, int] = {
    "15m": 15 * 60,
    "30m": 30 * 60,
    "1h": 3600,
    "4h": 4 * 3600,
    "1d": 86400,
}


def timeframe_seconds(timeframe: str) -> int:
    interval = TIMEFRAME_SECONDS.get(timeframe)
    if interval is None:
        raise ValueError(
            f"Timeframe '{timeframe}' không hợp lệ. Chọn: {', '.join(TIMEFRAME_SECONDS)}"
        )
    return interval


def window_start_ts(ts: int, interval_seconds: int) -> int:
    return (int(ts) // interval_seconds) * interval_seconds


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def aggregate_weighted_events(
    weighted_col: Collection,
    agg_col: Collection,
    *,
    timeframe: str = "1h",
    coin_id: str | None = None,
    since_ts: int | None = None,
) -> int:
    """Aggregate weighted_events theo coin_id + window_start.

    Output cố tình có alias `sentiment_score` để Stage 6 có thể dùng như social
    sentiment đã được influence-weighted.
    """
    interval = timeframe_seconds(timeframe)

    query: dict[str, Any] = {
        "coin_id": {"$exists": True, "$ne": None},
        "timestamp": {"$exists": True, "$ne": None},
    }
    if coin_id:
        query["coin_id"] = coin_id.upper()
    if since_ts is not None:
        query["timestamp"] = {"$gte": int(since_ts)}

    events = list(weighted_col.find(query))
    if not events:
        return 0

    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        cid = event.get("coin_id")
        ts = event.get("timestamp")
        if not cid or ts is None:
            continue
        ws = window_start_ts(int(ts), interval)
        buckets[(str(cid).upper(), ws)].append(event)

    upserted = 0
    for (cid, ws), bucket in buckets.items():
        social_volume = len(bucket)
        sentiment_scores = [_safe_float(e.get("sentiment_score")) for e in bucket]
        influence_weights = [_safe_float(e.get("influence_weight")) for e in bucket]
        weighted_sentiments = [_safe_float(e.get("weighted_sentiment")) for e in bucket]
        labels = [str(e.get("sentiment_label") or "neutral").lower() for e in bucket]

        total_influence = sum(influence_weights)
        total_weighted_sentiment = sum(weighted_sentiments)

        avg_sentiment = sum(sentiment_scores) / social_volume if social_volume else 0.0
        influence_weighted_sentiment = (
            total_weighted_sentiment / total_influence if total_influence > 0 else 0.0
        )

        window_start = datetime.fromtimestamp(ws, tz=timezone.utc)
        window_end = datetime.fromtimestamp(ws + interval, tz=timezone.utc)

        doc = {
            "coin_id": cid,
            "timeframe": timeframe,
            "timestamp": window_start,
            "window_start": window_start,
            "window_end": window_end,
            "social_volume": social_volume,
            "event_count": social_volume,
            "avg_sentiment": round(avg_sentiment, 6),
            "influence_weighted_sentiment": round(influence_weighted_sentiment, 6),
            # Alias cho Stage 6: scoring thường đọc `sentiment_score`.
            "sentiment_score": round(influence_weighted_sentiment, 6),
            "total_influence": round(total_influence, 6),
            "avg_influence": round(total_influence / social_volume, 6) if social_volume else 0.0,
            "max_influence": round(max(influence_weights), 6) if influence_weights else 0.0,
            "positive_count": labels.count("positive"),
            "neutral_count": labels.count("neutral"),
            "negative_count": labels.count("negative"),
            "updated_at": datetime.now(timezone.utc),
        }

        agg_col.update_one(
            {"coin_id": cid, "timeframe": timeframe, "window_start": window_start},
            {"$set": doc},
            upsert=True,
        )
        upserted += 1

    return upserted
