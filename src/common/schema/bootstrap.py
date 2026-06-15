"""Idempotent MongoDB collection + validator + index bootstrap.

Chạy an toàn nhiều lần (idempotent):
  1. Tạo collection + gắn $jsonSchema validator
  2. Ensure tất cả index theo bảng phase-01 §2.2

Gọi qua: python scripts/bootstrap_db.py hoặc bootstrap_indexes(db)
"""

from __future__ import annotations

from typing import Any

from motor.motor_asyncio import AsyncIOMotorDatabase

from src.common.schema.validators import COLLECTION_VALIDATORS

# moderate = chỉ validate insert/update mới, không re-validate doc cũ
# error    = reject document sai schema (WriteError 121)
_VALIDATION_OPTS: dict[str, Any] = {
    "validationLevel": "moderate",
    "validationAction": "error",
}


async def _ensure_collections(db: AsyncIOMotorDatabase) -> None:
    """Tạo collection mới hoặc cập nhật validator qua collMod nếu đã tồn tại."""
    existing = set(await db.list_collection_names())
    for name, validator in COLLECTION_VALIDATORS.items():
        if name not in existing:
            await db.create_collection(name, validator=validator, **_VALIDATION_OPTS)
        else:
            await db.command("collMod", name, validator=validator, **_VALIDATION_OPTS)


async def _ensure_indexes(db: AsyncIOMotorDatabase) -> int:
    """Ensure index theo tên — create_index idempotent, không tạo trùng."""
    count = 0

    async def _idx(collection: str, keys: list, **kwargs: Any) -> None:
        nonlocal count
        await db[collection].create_index(keys, **kwargs)
        count += 1

    # Stage 1 — dedup ingest: sparse cho phép doc không có external_id
    await _idx("raw_events", [("source", 1), ("external_id", 1)],
               unique=True, sparse=True, name="uq_source_extid")
    await _idx("raw_events", [("timestamp", 1)], name="idx_timestamp")

    # clean_events
    await _idx("clean_events", [("event_id", 1)], unique=True, name="uq_event_id")
    await _idx("clean_events", [("timestamp", 1)], name="idx_timestamp")

    # dropped_events
    await _idx("dropped_events", [("event_id", 1)], name="idx_event_id")
    await _idx("dropped_events", [("drop_stage", 1)], name="idx_drop_stage")

    # Stage 3 — fan-out: 1 post có thể map nhiều coin, unique theo (parent, coin)
    await _idx("mapped_events", [("parent_event_id", 1), ("coin_id", 1)],
               unique=True, name="uq_parent_coin")
    await _idx("mapped_events", [("coin_id", 1)], name="idx_coin_id")

    # sentiment_events
    await _idx("sentiment_events", [("mapped_id", 1), ("coin_id", 1)],
               unique=True, name="uq_mapped_coin")
    await _idx("sentiment_events", [("coin_id", 1), ("timestamp", 1)],
               name="idx_coin_timestamp")

    # sentiment_aggregates
    await _idx("sentiment_aggregates", [("coin_id", 1), ("window_start", 1)],
               name="idx_coin_window")

    # weighted_events
    await _idx("weighted_events", [("source_event_key", 1)],
               unique=True, name="uq_source_event_key")

    # Stage 5 — aggregate window: unique key cho upsert_stage()
    await _idx("influence_aggregates",
               [("coin_id", 1), ("timeframe", 1), ("window_start", 1)],
               unique=True, name="uq_agg_window")

    # scoring_signals
    await _idx("scoring_signals", [("signal_id", 1)], unique=True, name="uq_signal_id")
    await _idx("scoring_signals", [("coin_id", 1), ("timestamp", -1)],
               name="idx_coin_timestamp")

    # market_ohlcv cache (L-02)
    await _idx("market_ohlcv",
               [("coin_id", 1), ("timeframe", 1), ("timestamp", 1)],
               unique=True, name="uq_market_candle")

    # analysis_reports
    await _idx("analysis_reports", [("session_id", 1)], name="idx_session_id")
    await _idx("analysis_reports", [("coin_id", 1), ("generated_at", -1)],
               name="idx_coin_generated")

    # analysis_sessions
    await _idx("analysis_sessions", [("created_at", -1)], name="idx_created_at")
    await _idx("analysis_sessions", [("job_id", 1)], name="idx_job_id")

    # Chat — query lịch sử theo session, sort theo thời gian (FR-13)
    await _idx("chat_messages", [("session_id", 1), ("created_at", 1)],
               name="idx_session_created")

    # pipeline_jobs
    await _idx("pipeline_jobs", [("session_id", 1)], name="idx_session_id")
    await _idx("pipeline_jobs", [("status", 1), ("started_at", -1)],
               name="idx_status_started")

    # pipeline_stage_runs
    await _idx("pipeline_stage_runs", [("job_id", 1), ("stage", 1)],
               name="idx_job_stage")

    return count


async def bootstrap_indexes(db: AsyncIOMotorDatabase) -> int:
    """Entry point: collections + validators + indexes. Trả về số lần gọi create_index."""
    await _ensure_collections(db)
    return await _ensure_indexes(db)
