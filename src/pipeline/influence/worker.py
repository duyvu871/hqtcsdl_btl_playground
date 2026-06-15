"""Stage 5 worker — wire influence service vào Redis Streams runtime.

Pattern P2+P4:
  influence_processor → weighted_event persist → aggregate upsert → scoring trigger
"""

from __future__ import annotations

import logging
from typing import Any

from src.common.redis_client import get_redis
from src.pipeline._persist import insert_weighted_event, upsert_influence_aggregate
from src.pipeline._runtime.session_context import coin_matches, get_session_context
from src.pipeline.influence.service import InfluencePipeline, get_influence_pipeline

logger = logging.getLogger(__name__)


async def influence_processor(payload: dict[str, Any], fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage influence:
      1. Nhận sentiment_event từ stage:influence:in
      2. Tính influence_weight → weighted_events
      3. Upsert influence_aggregates
      4. Trả scoring trigger → stage:scoring:in
    """
    session_id = fields.get("session_id", "")
    pipeline = get_influence_pipeline()
    if session_id:
        redis = await get_redis()
        ctx = await get_session_context(redis, session_id)
        if ctx:
            if not coin_matches(payload.get("coin_id"), ctx["coin_id"]):
                logger.debug(
                    "Influence skip %s — session target %s",
                    payload.get("coin_id"),
                    ctx["coin_id"],
                )
                return []
            pipeline = InfluencePipeline(timeframe=ctx["timeframe"])

    weighted = pipeline.weight(payload)

    w_result = await insert_weighted_event(weighted)
    if w_result == "skipped":
        logger.debug("Skip duplicate weighted %s", weighted.get("source_event_key"))
        return []

    aggregate = await pipeline.rollup(weighted)
    if aggregate:
        await upsert_influence_aggregate(aggregate)
        weight = float(weighted.get("influence_weight", 0))
        vol = int(aggregate.get("social_volume") or 0)
        logger.debug(
            "Influence %s window %s: weight=%.3f vol=%d",
            aggregate.get("coin_id"),
            aggregate.get("window_start"),
            weight,
            vol,
        )
        trigger = await pipeline.build_trigger(aggregate)
        trigger["_summary"] = {
            "influence_weight": round(weight, 4),
            "social_volume": vol,
            "coin_id": aggregate.get("coin_id"),
            "window": str(aggregate.get("window_start", ""))[:16],
        }
        return [trigger]

    return []
