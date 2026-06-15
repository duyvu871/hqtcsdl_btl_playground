"""Tạo analysis session, init Redis state, planning + kickoff Stage 1."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.common.mongo_client import get_db
from src.common.redis_client import get_redis
from src.pipeline._runtime.emit import emit, utcnow_iso
from src.pipeline._runtime.keys import MAXLEN, in_stream, state_key
from src.pipeline._runtime.worker import publish_entry
from src.orchestrator.planning import emit_planning, utcnow


def build_kickoff_payload(
    coin_id: str,
    timeframe: str,
    *,
    sources: list[str] | None = None,
) -> dict[str, Any]:
    """Payload kickoff cho stage:ingest:in."""
    return {
        "type": "session_start",
        "coin_id": coin_id.upper(),
        "timeframe": timeframe,
        "sources": sources or ["twitter", "news-av", "news-yahoo"],
    }


def new_job_id() -> str:
    return f"job-{datetime.now(timezone.utc):%Y%m%d-%H%M%S}"


async def create_session(
    coin_id: str,
    timeframe: str,
    *,
    sources: list[str] | None = None,
    user_message: str | None = None,
) -> dict[str, str]:
    """
    Tạo session E2E:
      1. analysis_sessions + pipeline_jobs MongoDB
      2. Redis Hash session:{id}:state
      3. Planning phase (7 steps)
      4. Kickoff stage:ingest:in
    """
    session_id = str(uuid.uuid4())
    job_id = new_job_id()
    now = utcnow()
    coin = coin_id.upper()

    db = await get_db()
    redis = await get_redis()

    await db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": coin,
        "timeframe": timeframe,
        "job_id": job_id,
        "status": "pending",
        "created_at": now,
    })

    await db.pipeline_jobs.insert_one({
        "job_id": job_id,
        "session_id": session_id,
        "status": "pending",
        "started_at": now,
        "stages": [],
    })

    if user_message:
        await db.chat_messages.insert_one({
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "user",
            "type": "user",
            "content": user_message,
            "metadata": {"coin_id": coin, "timeframe": timeframe},
            "created_at": now,
        })

    await redis.hset(
        state_key(session_id),
        mapping={
            "status": "created",
            "coin_id": coin,
            "timeframe": timeframe,
            "job_id": job_id,
            "started_at": utcnow_iso(),
        },
    )

    await redis.hset(state_key(session_id), "status", "planning")
    await emit_planning(redis, session_id, job_id=job_id)

    kickoff = build_kickoff_payload(coin, timeframe, sources=sources)
    trace_id = str(uuid.uuid4())
    await publish_entry(
        redis,
        "ingest",
        kickoff,
        session_id=session_id,
        job_id=job_id,
        trace_id=trace_id,
        produced_by="orchestrator",
    )

    await redis.hset(state_key(session_id), "status", "running")
    await db.analysis_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": "running"}},
    )
    await db.pipeline_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"status": "running"}},
    )

    await emit(
        redis,
        session_id,
        "session_started",
        {"coin_id": coin, "timeframe": timeframe, "job_id": job_id},
        job_id=job_id,
    )

    return {"session_id": session_id, "job_id": job_id, "trace_id": trace_id}
