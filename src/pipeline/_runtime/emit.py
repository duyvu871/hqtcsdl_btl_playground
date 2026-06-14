"""Emit control events vào session:{id}:events control bus."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.pipeline._runtime.keys import CTL_MAXLEN, ctl_stream


def utcnow_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


async def emit(
    redis: aioredis.Redis,
    session_id: str,
    event_type: str,
    data: dict[str, Any],
    *,
    job_id: str = "",
) -> str:
    """XADD control event — Orchestrator/WS đọc stream này để cập nhật UI."""
    return await redis.xadd(
        ctl_stream(session_id),
        {
            "event_type": event_type,
            "session_id": session_id,
            "job_id": job_id,
            "data": json.dumps(data),
            "ts": utcnow_iso(),
        },
        maxlen=CTL_MAXLEN,
        approximate=True,
    )
