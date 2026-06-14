"""Stage 3 worker — wire NER service vào Redis Streams runtime.

Pattern P2+P3+P4:
  ner_processor → fan-out list[mapped_doc] → harness XADD stage:sentiment:in
  Không có mention → trả [] (không fan-out)
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline._persist import insert_mapped_event
from src.pipeline.ner.service import get_ner_pipeline

logger = logging.getLogger(__name__)


async def ner_processor(payload: dict[str, Any], _fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage ner:
      1. Nhận clean_event từ stage:ner:in
      2. Hybrid map coin mentions
      3. Ghi mapped_events (skip duplicate parent+coin)
      4. Trả docs mới insert → stage:sentiment:in
    """
    pipeline = get_ner_pipeline()
    outcome, docs = pipeline.process(payload)

    if not docs:
        logger.debug("NER no mentions: %s", payload.get("event_id"))
        return []

    persisted: list[dict[str, Any]] = []
    for doc in docs:
        result = await insert_mapped_event(doc)
        if result == "inserted":
            persisted.append(doc)
        else:
            logger.debug(
                "Skip duplicate mapped %s/%s",
                doc.get("parent_event_id"),
                doc.get("coin_id"),
            )

    logger.info(
        "NER: %s → %d mentions, %d persisted",
        payload.get("event_id"),
        len(outcome.mentions),
        len(persisted),
    )
    return persisted
