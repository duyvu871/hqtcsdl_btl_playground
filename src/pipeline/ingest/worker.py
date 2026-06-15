"""Stage 1 worker — wire ingest service vào Redis Streams runtime.

Pattern P2+P3:
  ingest_processor = processor fn truyền vào process_batch("ingest", ...)
  Harness tự XADD từng doc → stage:filter:in sau khi processor trả về.
"""

from __future__ import annotations

import logging
from typing import Any

from src.pipeline._persist import insert_raw_event
from src.pipeline.ingest.service import collect_from_kickoff

logger = logging.getLogger(__name__)


async def ingest_processor(payload: dict[str, Any], _fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage ingest:
      1. Gọi collectors theo kickoff payload
      2. Ghi raw_events (skip duplicate)
      3. Trả docs để harness XADD stage:filter:in
    """
    events = collect_from_kickoff(payload)
    persisted: list[dict[str, Any]] = []

    source_counts: dict[str, int] = {}
    for doc in events:
        result = await insert_raw_event(doc)
        if result == "inserted":
            persisted.append(doc)
            src = str(doc.get("source", "unknown"))
            source_counts[src] = source_counts.get(src, 0) + 1
        else:
            logger.debug("Skip duplicate raw_event %s", doc.get("event_id"))

    logger.info("Ingest: %d collected, %d persisted", len(events), len(persisted))

    if persisted:
        persisted[0]["_summary"] = {
            "records_out": len(persisted),
            "sources": source_counts,
        }
    return persisted
