"""Stage worker runtime — XREADGROUP → process → persist → XADD → XACK.

At-least-once delivery: XACK chỉ sau khi persist + fan-out downstream thành công.
Tham chiếu: docs/kien-truc-he-thong.md §5.5, §5.6, §13.2
"""

from __future__ import annotations

import json
import logging
import os
import socket
from collections.abc import Awaitable, Callable
from typing import Any

import redis.asyncio as aioredis
from redis.exceptions import ResponseError

from src.common.config import settings
from src.pipeline._runtime.emit import emit, utcnow_iso
from src.pipeline._runtime.keys import (
    MAXLEN,
    NEXT_STREAM,
    dlq_stream,
    group,
    in_stream,
    state_key,
)

logger = logging.getLogger(__name__)

# processor(payload_dict, raw_fields) → output doc(s)
ProcessorFn = Callable[[dict[str, Any], dict[str, str]], Awaitable[list[dict[str, Any]] | dict[str, Any]]]
# persist_fn(stage, doc) — noop cho echo/test; pipeline stages gắn ở phase 3+
PersistFn = Callable[[str, dict[str, Any]], Awaitable[None]]


def default_consumer(name: str | None = None) -> str:
    """Consumer name pattern: {hostname}-{pid}"""
    return name or f"{socket.gethostname()}-{os.getpid()}"


def build_entry(
    payload: dict[str, Any],
    *,
    session_id: str,
    job_id: str,
    trace_id: str,
    produced_by: str,
    retry_count: int = 0,
) -> dict[str, str]:
    """Tạo flat string fields cho transport entry (§5.3)."""
    return {
        "session_id": session_id,
        "job_id": job_id,
        "trace_id": trace_id,
        "produced_by": produced_by,
        "produced_at": utcnow_iso(),
        "schema_version": "v1",
        "payload": json.dumps(payload),
        "retry_count": str(retry_count),
    }


async def ensure_consumer_group(redis: aioredis.Redis, stage: str) -> None:
    """Tạo consumer group idempotent (BUSYGROUP = đã tồn tại)."""
    stream = in_stream(stage)
    grp = group(stage)
    try:
        await redis.xgroup_create(stream, grp, id="0", mkstream=True)
    except ResponseError as exc:
        if "BUSYGROUP" not in str(exc):
            raise


async def publish_entry(
    redis: aioredis.Redis,
    stage: str,
    payload: dict[str, Any],
    *,
    session_id: str,
    job_id: str,
    trace_id: str,
    produced_by: str = "orchestrator",
    retry_count: int = 0,
) -> str:
    """XADD entry vào stage:{name}:in — dùng cho orchestrator kick-off và tests."""
    fields = build_entry(
        payload,
        session_id=session_id,
        job_id=job_id,
        trace_id=trace_id,
        produced_by=produced_by,
        retry_count=retry_count,
    )
    return await redis.xadd(
        in_stream(stage),
        fields,
        maxlen=MAXLEN,
        approximate=True,
    )


async def _delivery_count(
    redis: aioredis.Redis,
    stream: str,
    grp: str,
    entry_id: str,
) -> int:
    """Số lần entry đã được deliver — dùng làm retry counter (PEL)."""
    pending = await redis.xpending_range(stream, grp, entry_id, entry_id, 1)
    if pending:
        return int(pending[0]["times_delivered"])
    return 1


async def _handle_failure(
    redis: aioredis.Redis,
    stage: str,
    entry_id: str,
    fields: dict[str, str],
    exc: Exception,
) -> None:
    """stage_failed → DLQ nếu đủ retry; ngược lại giữ entry trong PEL để reclaim."""
    session_id = fields["session_id"]
    job_id = fields.get("job_id", "")
    stream = in_stream(stage)
    grp = group(stage)

    await emit(
        redis,
        session_id,
        "stage_failed",
        {"stage": stage, "error": str(exc)},
        job_id=job_id,
    )

    deliveries = await _delivery_count(redis, stream, grp, entry_id)
    if deliveries >= settings.STREAM_MAX_RETRY:
        dlq_fields = {**fields, "error": str(exc), "retry_count": str(deliveries)}
        await redis.xadd(dlq_stream(stage), dlq_fields, maxlen=MAXLEN, approximate=True)
        await redis.xack(stream, grp, entry_id)
        logger.warning("Entry %s moved to DLQ after %d deliveries", entry_id, deliveries)


async def process_entry(
    redis: aioredis.Redis,
    stage: str,
    entry_id: str,
    fields: dict[str, str],
    processor: ProcessorFn,
    *,
    consumer: str,
    persist_fn: PersistFn | None = None,
    downstream: str | None = None,
) -> bool:
    """Xử lý một entry. Trả True nếu ack thành công."""
    session_id = fields["session_id"]
    job_id = fields.get("job_id", "")
    trace_id = fields["trace_id"]
    stream = in_stream(stage)
    grp = group(stage)

    payload = json.loads(fields["payload"])
    await emit(redis, session_id, "stage_started", {"stage": stage}, job_id=job_id)

    try:
        result = await processor(payload, fields)
        outputs = result if isinstance(result, list) else [result]

        if persist_fn:
            for doc in outputs:
                await persist_fn(stage, doc)

        next_stream = downstream if downstream is not None else NEXT_STREAM.get(stage)
        if next_stream:
            for doc in outputs:
                await redis.xadd(
                    next_stream,
                    build_entry(
                        doc,
                        session_id=session_id,
                        job_id=job_id,
                        trace_id=trace_id,
                        produced_by=f"stage:{stage}",
                    ),
                    maxlen=MAXLEN,
                    approximate=True,
                )

        await redis.xack(stream, grp, entry_id)
        await emit(
            redis,
            session_id,
            "stage_completed",
            {"stage": stage, "records_in": 1, "records_out": len(outputs)},
            job_id=job_id,
        )
        await redis.hincrby(state_key(session_id), f"{stage}_out", len(outputs))
        return True

    except Exception as exc:
        await _handle_failure(redis, stage, entry_id, fields, exc)
        return False


async def read_batch(
    redis: aioredis.Redis,
    stage: str,
    consumer: str,
    *,
    count: int = 64,
    block_ms: int = 5000,
) -> list[tuple[str, dict[str, str]]]:
    """XREADGROUP một batch từ stage:{name}:in."""
    stream = in_stream(stage)
    grp = group(stage)
    batches = await redis.xreadgroup(
        grp,
        consumer,
        {stream: ">"},
        count=count,
        block=block_ms,
    )
    messages: list[tuple[str, dict[str, str]]] = []
    if batches:
        for _stream_name, entries in batches:
            messages.extend(entries)
    return messages


async def process_batch(
    redis: aioredis.Redis,
    stage: str,
    processor: ProcessorFn,
    *,
    consumer: str | None = None,
    persist_fn: PersistFn | None = None,
    downstream: str | None = None,
    count: int = 64,
    block_ms: int = 0,
) -> int:
    """Đọc và xử lý một batch; trả số entry đã đọc (kể cả fail)."""
    cons = default_consumer(consumer)
    await ensure_consumer_group(redis, stage)
    messages = await read_batch(redis, stage, cons, count=count, block_ms=block_ms)

    for entry_id, fields in messages:
        await process_entry(
            redis,
            stage,
            entry_id,
            fields,
            processor,
            consumer=cons,
            persist_fn=persist_fn,
            downstream=downstream,
        )
    return len(messages)


async def reclaim_pending(
    redis: aioredis.Redis,
    stage: str,
    processor: ProcessorFn,
    *,
    consumer: str | None = None,
    persist_fn: PersistFn | None = None,
    downstream: str | None = None,
    min_idle_ms: int | None = None,
    count: int = 10,
) -> int:
    """XAUTOCLAIM entries idle quá lâu trong PEL — worker khác nhận lại để retry."""
    cons = default_consumer(consumer)
    stream = in_stream(stage)
    grp = group(stage)
    idle = min_idle_ms if min_idle_ms is not None else settings.STREAM_CLAIM_IDLE_MS

    await ensure_consumer_group(redis, stage)
    _next_id, claimed, _deleted = await redis.xautoclaim(
        stream,
        grp,
        cons,
        idle,
        "0-0",
        count=count,
    )

    processed = 0
    for entry_id, fields in claimed:
        if fields is None:
            continue
        await process_entry(
            redis,
            stage,
            entry_id,
            fields,
            processor,
            consumer=cons,
            persist_fn=persist_fn,
            downstream=downstream,
        )
        processed += 1
    return processed


async def run(
    stage: str,
    processor: ProcessorFn,
    *,
    consumer: str | None = None,
    persist_fn: PersistFn | None = None,
    downstream: str | None = None,
    reclaim_every: int = 10,
) -> None:
    """Vòng lặp worker chính — dùng trong production (chạy vô hạn)."""
    cons = default_consumer(consumer)
    await ensure_consumer_group(redis := await _get_redis(), stage)
    batches = 0

    while True:
        if reclaim_every and batches % reclaim_every == 0:
            await reclaim_pending(
                redis,
                stage,
                processor,
                consumer=cons,
                persist_fn=persist_fn,
                downstream=downstream,
            )

        await process_batch(
            redis,
            stage,
            processor,
            consumer=cons,
            persist_fn=persist_fn,
            downstream=downstream,
            block_ms=5000,
        )
        batches += 1


async def _get_redis() -> aioredis.Redis:
    from src.common.redis_client import get_redis

    return await get_redis()


async def pending_count(redis: aioredis.Redis, stage: str) -> int:
    """Tổng entry chưa ack trong PEL — dùng để verify tests."""
    stream = in_stream(stage)
    grp = group(stage)
    info = await redis.xpending(stream, grp)
    return int(info["pending"])
