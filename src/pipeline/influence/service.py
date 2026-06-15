"""Stage 5 business logic — influence weight + aggregate rollup."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from src.common.config import settings
from src.common.mongo_client import get_db
from src.pipeline.influence.aggregate import aggregate_for_event, fetch_recent_aggregates
from src.pipeline.influence.documents import (
    aggregate_to_social_row,
    build_scoring_trigger,
    build_weighted_event,
)


def _window_ts(value: Any) -> float:
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc).timestamp()
        return value.timestamp()
    if isinstance(value, (int, float)):
        return float(value)
    return 0.0


@dataclass
class InfluencePipeline:
    """Tính influence_weight, ghi weighted_events, rollup aggregates."""

    timeframe: str = settings.INFLUENCE_TIMEFRAME

    def weight(self, sentiment_event: dict[str, Any]) -> dict[str, Any]:
        return build_weighted_event(sentiment_event)

    async def rollup(self, weighted_event: dict[str, Any]) -> dict[str, Any] | None:
        db = await get_db()
        return await aggregate_for_event(db, weighted_event, timeframe=self.timeframe)

    async def build_trigger(self, aggregate: dict[str, Any]) -> dict[str, Any]:
        db = await get_db()
        coin_id = str(aggregate.get("coin_id") or "")
        history_docs = await fetch_recent_aggregates(
            db,
            coin_id,
            timeframe=self.timeframe,
            limit=settings.SCORING_OHLCV_LIMIT,
        )
        current_ws = _window_ts(aggregate.get("window_start"))
        if not any(_window_ts(doc.get("window_start")) == current_ws for doc in history_docs):
            history_docs.append(aggregate)
        history_docs.sort(key=lambda doc: _window_ts(doc.get("window_start")))
        social_history = [aggregate_to_social_row(doc) for doc in history_docs]
        return build_scoring_trigger(aggregate, social_history)

    async def process(self, sentiment_event: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any] | None, dict[str, Any] | None]:
        """Trả (weighted_event, aggregate, scoring_trigger)."""
        weighted = self.weight(sentiment_event)
        aggregate = await self.rollup(weighted)
        trigger = await self.build_trigger(aggregate) if aggregate else None
        return weighted, aggregate, trigger


_pipeline: InfluencePipeline | None = None


def get_influence_pipeline() -> InfluencePipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = InfluencePipeline()
    return _pipeline


def reset_influence_pipeline() -> None:
    global _pipeline
    _pipeline = None
