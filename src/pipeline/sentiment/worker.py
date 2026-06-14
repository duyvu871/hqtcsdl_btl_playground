"""Stage 4 worker — wire sentiment service vào Redis Streams runtime.

Pattern P2+P4:
  sentiment_processor → 1 mapped in → 1 sentiment_event out (terminal fan-out item)
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline._persist import insert_sentiment_event
from src.pipeline.sentiment.service import get_sentiment_pipeline

logger = logging.getLogger(__name__)


async def sentiment_processor(payload: dict[str, Any], _fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage sentiment:
      1. Nhận mapped_event từ stage:sentiment:in
      2. Score sentiment (AV bypass / rule / FinBERT)
      3. Ghi sentiment_events
      4. Trả doc → stage:influence:in
    """
    pipeline = get_sentiment_pipeline()
    doc = pipeline.process(payload)
    result = await insert_sentiment_event(doc)

    if result == "inserted":
        logger.debug(
            "Sentiment %s %s: %s (%.2f)",
            doc.get("coin_id"),
            doc.get("method"),
            doc.get("sentiment_label"),
            doc.get("sentiment_score", 0),
        )
        return [doc]

    logger.debug("Skip duplicate sentiment %s/%s", doc.get("mapped_id"), doc.get("coin_id"))
    return []
