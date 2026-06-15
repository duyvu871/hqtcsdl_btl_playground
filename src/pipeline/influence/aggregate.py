"""Rollup weighted_events → influence_aggregates theo coin + timeframe + window."""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.common.config import settings

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


def _normalize_ts(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    return None


def build_aggregate_doc(
    cid: str,
    ws: int,
    bucket: list[dict[str, Any]],
    *,
    timeframe: str,
) -> dict[str, Any]:
    interval = timeframe_seconds(timeframe)
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

    return {
        "coin_id": cid,
        "timeframe": timeframe,
        "timestamp": window_start,
        "window_start": window_start,
        "window_end": window_end,
        "social_volume": social_volume,
        "event_count": social_volume,
        "avg_sentiment": round(avg_sentiment, 6),
        "influence_weighted_sentiment": round(influence_weighted_sentiment, 6),
        "sentiment_score": round(influence_weighted_sentiment, 6),
        "total_influence": round(total_influence, 6),
        "avg_influence": round(total_influence / social_volume, 6) if social_volume else 0.0,
        "max_influence": round(max(influence_weights), 6) if influence_weights else 0.0,
        "positive_count": labels.count("positive"),
        "neutral_count": labels.count("neutral"),
        "negative_count": labels.count("negative"),
        "updated_at": datetime.now(timezone.utc),
    }


async def aggregate_weighted_events(
    db: AsyncIOMotorDatabase,
    *,
    timeframe: str | None = None,
    coin_id: str | None = None,
    since_ts: int | None = None,
) -> list[dict[str, Any]]:
    """Aggregate weighted_events theo coin_id + window_start. Trả danh sách agg docs."""
    tf = timeframe or settings.INFLUENCE_TIMEFRAME
    interval = timeframe_seconds(tf)

    query: dict[str, Any] = {
        "coin_id": {"$exists": True, "$ne": None},
        "timestamp": {"$exists": True, "$ne": None},
    }
    if coin_id:
        query["coin_id"] = coin_id.upper()
    if since_ts is not None:
        query["timestamp"] = {"$gte": int(since_ts)}

    events = await db.weighted_events.find(query).to_list(length=10_000)
    if not events:
        return []

    buckets: dict[tuple[str, int], list[dict[str, Any]]] = defaultdict(list)
    for event in events:
        cid = event.get("coin_id")
        ts = _normalize_ts(event.get("timestamp"))
        if not cid or ts is None:
            continue
        ws = window_start_ts(ts, interval)
        buckets[(str(cid).upper(), ws)].append(event)

    docs: list[dict[str, Any]] = []
    for (cid, ws), bucket in buckets.items():
        docs.append(build_aggregate_doc(cid, ws, bucket, timeframe=tf))
    return docs


async def aggregate_for_event(
    db: AsyncIOMotorDatabase,
    weighted_event: dict[str, Any],
    *,
    timeframe: str | None = None,
) -> dict[str, Any] | None:
    """Tính lại aggregate cho window chứa weighted_event vừa insert."""
    coin_id = weighted_event.get("coin_id")
    ts = _normalize_ts(weighted_event.get("timestamp"))
    if not coin_id or ts is None:
        return None

    tf = timeframe or settings.INFLUENCE_TIMEFRAME
    interval = timeframe_seconds(tf)
    ws = window_start_ts(ts, interval)

    query = {
        "coin_id": str(coin_id).upper(),
        "timestamp": {"$gte": ws, "$lt": ws + interval},
    }
    bucket = await db.weighted_events.find(query).to_list(length=10_000)
    event_key = weighted_event.get("source_event_key")
    if not any(e.get("source_event_key") == event_key for e in bucket):
        bucket.append(weighted_event)
    if not bucket:
        return None

    return build_aggregate_doc(str(coin_id).upper(), ws, bucket, timeframe=tf)


async def fetch_recent_aggregates(
    db: AsyncIOMotorDatabase,
    coin_id: str,
    *,
    timeframe: str | None = None,
    limit: int = 48,
) -> list[dict[str, Any]]:
    """Lấy N aggregate gần nhất — pack vào scoring transport."""
    tf = timeframe or settings.INFLUENCE_TIMEFRAME
    cursor = (
        db.influence_aggregates.find({"coin_id": coin_id.upper(), "timeframe": tf})
        .sort("window_start", -1)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    rows.reverse()
    return rows
