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


async def insert_weighted_event(doc: dict) -> InsertResult:
    """Ghi weighted_events; skip nếu trùng source_event_key."""
    db = await get_db()
    try:
        await db.weighted_events.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("weighted_events duplicate: %s", doc.get("source_event_key"))
        return "skipped"


async def upsert_influence_aggregate(doc: dict) -> None:
    """Upsert influence_aggregates theo (coin_id, timeframe, window_start)."""
    db = await get_db()
    await db.influence_aggregates.update_one(
        {
            "coin_id": doc["coin_id"],
            "timeframe": doc["timeframe"],
            "window_start": doc["window_start"],
        },
        {"$set": doc},
        upsert=True,
    )


async def insert_scoring_signal(doc: dict) -> InsertResult:
    """Ghi scoring_signals; skip nếu trùng signal_id."""
    db = await get_db()
    try:
        await db.scoring_signals.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("scoring_signals duplicate: %s", doc.get("signal_id"))
        return "skipped"


async def upsert_market_ohlcv(
    coin_id: str,
    timeframe: str,
    candles: list[dict],
) -> int:
    """Cache OHLCV vào market_ohlcv (L-02). Trả số doc upserted."""
    from datetime import datetime, timezone

    db = await get_db()
    upserted = 0
    for candle in candles:
        ts = candle.get("timestamp")
        if ts is None:
            continue
        ts_int = int(ts) if isinstance(ts, (int, float)) else int(float(ts))
        doc = {
            "coin_id": coin_id.upper(),
            "timeframe": timeframe,
            "timestamp": ts_int,
            "close": float(candle["close"]),
            "volume": float(candle.get("volume", 0)),
            "updated_at": datetime.now(timezone.utc),
        }
        await db.market_ohlcv.update_one(
            {"coin_id": doc["coin_id"], "timeframe": timeframe, "timestamp": ts_int},
            {"$set": doc},
            upsert=True,
        )
        upserted += 1
    return upserted


async def insert_analysis_report(doc: dict) -> InsertResult:
    """Ghi analysis_reports; skip nếu trùng report_id."""
    db = await get_db()
    try:
        await db.analysis_reports.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("analysis_reports duplicate: %s", doc.get("report_id"))
        return "skipped"


async def insert_report_chat_message(doc: dict) -> InsertResult:
    """Ghi chat_messages type=report."""
    db = await get_db()
    try:
        await db.chat_messages.insert_one(doc)
        return "inserted"
    except DuplicateKeyError:
        logger.debug("chat_messages duplicate: %s", doc.get("message_id"))
        return "skipped"
