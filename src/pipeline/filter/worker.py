"""Stage 2 worker — wire filter service vào Redis Streams runtime.

Pattern P2+P3:
  filter_processor = processor fn truyền vào process_batch("filter", ...)
  PASS → trả [clean_doc], harness XADD stage:ner:in
  DROP → trả [], không fan-out downstream
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline._persist import insert_clean_event, insert_dropped_event
from src.pipeline.filter.service import get_filter_pipeline

logger = logging.getLogger(__name__)


async def filter_processor(payload: dict[str, Any], _fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage filter:
      1. Nhận raw_event từ stage:filter:in
      2. Chạy cascade L1→L2→L3
      3. PASS → ghi clean_events, trả doc cho stage:ner:in
      4. DROP → ghi dropped_events, trả [] (không fan-out)
    """
    pipeline = get_filter_pipeline()
    clean_doc, dropped_doc = pipeline.process(payload)

    if clean_doc:
        await insert_clean_event(clean_doc)
        logger.debug("Filter PASS: %s", clean_doc.get("event_id"))
        clean_doc["_summary"] = {
            "verdict": "pass",
            "drop_stage": None,
            "drop_reason": None,
        }
        return [clean_doc]

    # DROP: ghi audit, không đẩy xuống NER
    if dropped_doc:
        await insert_dropped_event(dropped_doc)
        logger.debug("Filter DROP %s/%s: %s", dropped_doc.get("drop_stage"), dropped_doc.get("drop_reason"), dropped_doc.get("event_id"))

    return []
