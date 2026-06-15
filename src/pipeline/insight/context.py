"""Load MongoDB context bổ sung cho Stage 7 insight."""

from __future__ import annotations

from typing import Any

from src.common.mongo_client import get_db


async def load_insight_context(
    signal: dict[str, Any],
    *,
    top_events_limit: int = 10,
) -> dict[str, Any]:
    """Query sentiment_events + influence_aggregates theo coin/timeframe."""
    db = await get_db()
    coin_id = str(signal.get("coin_id") or "BTC").upper()
    timeframe = str(signal.get("timeframe") or "1h")

    sentiments = (
        await db.sentiment_events.find({"coin_id": coin_id})
        .sort("timestamp", -1)
        .limit(top_events_limit)
        .to_list(top_events_limit)
    )

    aggregate = await db.influence_aggregates.find_one(
        {"coin_id": coin_id, "timeframe": timeframe},
        sort=[("window_start", -1)],
    )

    social_volume = int((aggregate or {}).get("social_volume", 0))
    weighted_sentiment = float(
        (aggregate or {}).get("sentiment_score")
        or (aggregate or {}).get("influence_weighted_sentiment", 0.0)
    )

    metrics = signal.get("metrics") or {}
    execution = signal.get("execution") or {}

    return {
        "coin_id": coin_id,
        "timeframe": timeframe,
        "action": signal.get("action", "HOLD"),
        "alpha": metrics.get("galaxy_alpha_score", 0),
        "safety": metrics.get("galaxy_safety_score", 0),
        "confidence": metrics.get("confidence", 0),
        "social_volume": social_volume,
        "weighted_sentiment": weighted_sentiment,
        "target_price": execution.get("target_price"),
        "stop_loss": execution.get("stop_loss"),
        "top_events": sentiments,
        "aggregate": aggregate,
    }
