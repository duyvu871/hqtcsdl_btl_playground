"""Stage 5 worker — wire influence service vào Redis Streams runtime.

Pattern P2+P4:
  influence_processor → weighted_event persist → aggregate upsert → scoring trigger
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline._persist import insert_weighted_event, upsert_influence_aggregate
from src.pipeline.influence.service import get_influence_pipeline

logger = logging.getLogger(__name__)


async def influence_processor(payload: dict[str, Any], _fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage influence:
      1. Nhận sentiment_event từ stage:influence:in
      2. Tính influence_weight → weighted_events
      3. Upsert influence_aggregates
      4. Trả scoring trigger → stage:scoring:in
    """
    pipeline = get_influence_pipeline()
    weighted = pipeline.weight(payload)

    w_result = await insert_weighted_event(weighted)
    if w_result == "skipped":
        logger.debug("Skip duplicate weighted %s", weighted.get("source_event_key"))
        return []

    aggregate = await pipeline.rollup(weighted)
    if aggregate:
        await upsert_influence_aggregate(aggregate)
        logger.debug(
            "Influence %s window %s: weight=%.3f vol=%d",
            aggregate.get("coin_id"),
            aggregate.get("window_start"),
            weighted.get("influence_weight", 0),
            aggregate.get("social_volume", 0),
        )
        trigger = await pipeline.build_trigger(aggregate)
        return [trigger]

    return []
