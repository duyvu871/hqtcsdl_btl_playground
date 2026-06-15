"""Monitor control stream — state machine + finalize snapshot."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.common.config import settings
from src.common.mongo_client import get_db
from src.common.redis_client import get_redis
from src.pipeline._runtime.emit import emit
from src.pipeline._runtime.keys import STAGE_ORDER, ctl_stream, orch_cursor_key, state_key
from src.orchestrator.planning import utcnow

logger = logging.getLogger(__name__)

# Stage 6 là terminal cho P6 (chưa Stage 7 Insight)
ETL_STAGES: list[str] = [s for s in STAGE_ORDER if s != "insight"]


def _stream_id(value: Any) -> str:
    """Chuẩn hóa Redis stream ID — Pyright-safe cho xread."""
    if value is None:
        return "0-0"
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _ctl_fields(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {_as_str(k): _as_str(v) for k, v in raw.items()}


def _xread_messages(entries: Any) -> list[tuple[str, dict[str, str]]]:
    """Parse kết quả XREAD — bỏ qua batch/field None (stub redis-py)."""
    if not entries:
        return []
    first = entries[0]
    if not isinstance(first, (list, tuple)) or len(first) < 2:
        return []
    batch = first[1]
    if not batch:
        return []
    messages: list[tuple[str, dict[str, str]]] = []
    for item in batch:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        entry_id, fields = item[0], item[1]
        if fields is None:
            continue
        messages.append((_stream_id(entry_id), _ctl_fields(fields)))
    return messages


def _xrange_messages(entries: Any) -> list[tuple[str, dict[str, str]]]:
    """Parse kết quả XRANGE."""
    messages: list[tuple[str, dict[str, str]]] = []
    if not entries:
        return messages
    for item in entries:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        entry_id, fields = item[0], item[1]
        if fields is None:
            continue
        messages.append((_stream_id(entry_id), _ctl_fields(fields)))
    return messages


def _cursor_ttl_seconds() -> int:
    return settings.SESSION_TTL_DAYS * 86400


async def handle_control_event(
    redis: aioredis.Redis,
    session_id: str,
    job_id: str,
    event_type: str,
    data: dict[str, Any],
) -> str | None:
    """
    Xử lý một control event — cập nhật Redis state + side effects.
    Trả status mới nếu đổi; None nếu không đổi / chưa terminal.
    """
    sk = state_key(session_id)
    db = await get_db()

    if event_type == "stage_completed":
        stage = str(data.get("stage", ""))
        await redis.hset(sk, "current_stage", stage)
        if stage == "scoring":
            await redis.hset(sk, "status", "insight_streaming")
            await finalize_session(session_id, job_id, through_stage="scoring")
            return "insight_streaming"
        return None

    if event_type == "stage_failed":
        await redis.hset(sk, "status", "failed_partial")
        error = str(data.get("error", "unknown"))
        await db.analysis_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "failed"}},
        )
        await db.pipeline_jobs.update_one(
            {"job_id": job_id},
            {"$set": {"status": "failed", "finished_at": utcnow()}},
        )
        await db.chat_messages.insert_one({
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "assistant",
            "type": "error",
            "content": f"Stage failed: {error}",
            "metadata": data,
            "created_at": utcnow(),
        })
        return "failed_partial"

    if event_type == "signal_ready":
        await db.chat_messages.insert_one({
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "assistant",
            "type": "signal_card",
            "content": (
                f"Signal {data.get('action')} — "
                f"Alpha {data.get('alpha')} / Safety {data.get('safety')}"
            ),
            "metadata": data,
            "created_at": utcnow(),
        })
        return None

    if event_type == "report_done":
        await redis.hset(sk, "status", "completed")
        await finalize_session(session_id, job_id, complete_session=True)
        await emit(redis, session_id, "session_completed", {}, job_id=job_id)
        return "completed"

    return None


async def finalize_session(
    session_id: str,
    job_id: str,
    *,
    through_stage: str | None = None,
    complete_session: bool = False,
) -> None:
    """Snapshot Redis Hash → pipeline_jobs + pipeline_stage_runs (+ sessions nếu hoàn tất)."""
    redis = await get_redis()
    db = await get_db()
    state = await redis.hgetall(state_key(session_id))
    now = utcnow()

    if through_stage:
        end_idx = STAGE_ORDER.index(through_stage)
        stages = STAGE_ORDER[: end_idx + 1]
    elif complete_session:
        stages = list(STAGE_ORDER)
    else:
        stages = list(ETL_STAGES)

    job_status = "completed" if complete_session else "running"
    existing = await db.pipeline_jobs.find_one({"job_id": job_id})
    started_at = (existing or {}).get("started_at") or now

    job_update: dict[str, Any] = {
        "job_id": job_id,
        "session_id": session_id,
        "status": job_status,
        "started_at": started_at,
        "coin_id": state.get("coin_id"),
        "timeframe": state.get("timeframe"),
        "current_stage": state.get("current_stage"),
    }
    if complete_session:
        job_update["finished_at"] = now

    for raw_key, value in state.items():
        key = raw_key.decode() if isinstance(raw_key, bytes) else str(raw_key)
        if key.endswith("_in") or key.endswith("_out") or key.endswith("_duration_ms"):
            job_update[key] = value

    await db.pipeline_jobs.update_one(
        {"job_id": job_id},
        {"$set": job_update},
        upsert=True,
    )

    for stage in stages:
        if stage == "insight" and not complete_session:
            continue
        await db.pipeline_stage_runs.update_one(
            {"job_id": job_id, "stage": stage},
            {
                "$set": {
                    "run_id": f"{job_id}:{stage}",
                    "job_id": job_id,
                    "stage": stage,
                    "records_in": int(state.get(f"{stage}_in", 0)),
                    "records_out": int(state.get(f"{stage}_out", 0)),
                    "duration_ms": int(state.get(f"{stage}_duration_ms", 0)),
                    "status": "completed",
                }
            },
            upsert=True,
        )

    if complete_session:
        await db.analysis_sessions.update_one(
            {"session_id": session_id},
            {"$set": {"status": "completed", "completed_at": now}},
        )


async def monitor_session(
    session_id: str,
    job_id: str,
    *,
    block_ms: int = 30_000,
) -> str:
    """
    Vòng lặp XREAD control stream — trả status terminal.
    Terminal: insight_streaming (P6), completed (report_done), failed_partial.
    """
    redis = await get_redis()
    stream = ctl_stream(session_id)
    cursor_key = orch_cursor_key(session_id)

    last_id = _stream_id(await redis.get(cursor_key))
    await redis.hset(state_key(session_id), mapping={"status": "running", "job_id": job_id})

    while True:
        entries = await redis.xread({stream: last_id}, block=block_ms, count=100)
        for entry_id, fields in _xread_messages(entries):
            last_id = entry_id
            await redis.set(cursor_key, last_id, ex=_cursor_ttl_seconds())

            event_type = fields.get("event_type", "")
            raw_data = fields.get("data", "{}")
            try:
                data = json.loads(raw_data)
            except json.JSONDecodeError:
                data = {}

            terminal = await handle_control_event(redis, session_id, job_id, event_type, data)
            if terminal in ("completed", "failed_partial", "insight_streaming"):
                logger.info("Session %s terminal status: %s", session_id, terminal)
                return terminal


async def drain_control_events(
    session_id: str,
    job_id: str,
    *,
    redis: aioredis.Redis | None = None,
) -> str | None:
    """Drain toàn bộ control events hiện có — dùng cho tests (không block)."""
    r = redis or await get_redis()
    stream = ctl_stream(session_id)
    cursor_key = orch_cursor_key(session_id)
    terminal: str | None = None

    entries = await r.xrange(stream)
    for entry_id, fields in _xrange_messages(entries):
        await r.set(cursor_key, entry_id, ex=_cursor_ttl_seconds())
        event_type = fields.get("event_type", "")
        data = json.loads(fields.get("data", "{}"))
        result = await handle_control_event(r, session_id, job_id, event_type, data)
        if result:
            terminal = result

    return terminal
