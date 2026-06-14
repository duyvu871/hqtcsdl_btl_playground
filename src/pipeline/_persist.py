"""MongoDB insert helpers — dedup qua DuplicateKeyError (pattern playground).

Dùng insert_one + catch DuplicateKeyError thay vì upsert:
  - raw_events: dedup theo (source, external_id) — TC-09
  - clean_events: dedup theo event_id
"""

from __future__ import annotations

import logging
from typing import Literal

from pymongo.errors import DuplicateKeyError

from src.common.mongo_client import get_db

logger = logging.getLogger(__name__)

InsertResult = Literal["inserted", "skipped"]


async def insert_raw_event(doc: dict) -> InsertResult:
    """Ghi raw_events; skip nếu trùng (source, external_id) — TC-09."""
    db = await get_db()
    try:
        await db.raw_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("raw_events duplicate: %s/%s", doc.get("source"), doc.get("external_id"))
        return "skipped"


async def insert_clean_event(doc: dict) -> InsertResult:
    """Ghi clean_events; skip nếu trùng event_id."""
    db = await get_db()
    try:
        await db.clean_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        return "skipped"


async def insert_dropped_event(doc: dict) -> InsertResult:
    """Ghi dropped_events audit trail."""
    db = await get_db()
    try:
        await db.dropped_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        return "skipped"


async def insert_mapped_event(doc: dict) -> InsertResult:
    """Ghi mapped_events; skip nếu trùng (parent_event_id, coin_id) — T4-02."""
    db = await get_db()
    try:
        await db.mapped_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug(
            "mapped_events duplicate: %s/%s",
            doc.get("parent_event_id"),
            doc.get("coin_id"),
        )
        return "skipped"


async def insert_sentiment_event(doc: dict) -> InsertResult:
    """Ghi sentiment_events; skip nếu trùng sentiment_id."""
    db = await get_db()
    try:
        await db.sentiment_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("sentiment_events duplicate: %s", doc.get("sentiment_id"))
        return "skipped"
