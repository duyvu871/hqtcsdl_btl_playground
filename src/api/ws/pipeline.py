"""WebSocket /ws/pipeline — broadcast job events từ active sessions."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from fastapi import APIRouter, WebSocket

from src.common.mongo_client import get_db
from src.common.redis_client import get_redis
from src.pipeline._runtime.keys import ctl_stream
from src.api.ws._helpers import ctl_fields, envelope, send_event, stream_id, xread_messages, xread_streams

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

WS_BLOCK_MS = 2_000
PIPELINE_EVENT_TYPES = frozenset({
    "session_started",
    "stage_started",
    "stage_progress",
    "stage_completed",
    "stage_failed",
    "signal_ready",
    "report_done",
    "session_completed",
})


async def _active_session_streams(limit: int = 20) -> dict[str, str]:
    """Map stream → last_id cho các session đang chạy / gần đây."""
    db = await get_db()
    cursor = (
        db.pipeline_jobs.find({"status": {"$in": ["running", "pending"]}})
        .sort("started_at", -1)
        .limit(limit)
    )
    jobs = await cursor.to_list(length=limit)
    streams: dict[str, str] = {}
    for job in jobs:
        sid = job.get("session_id")
        if sid:
            streams[ctl_stream(sid)] = "0-0"
    if streams:
        return streams

    cursor = db.pipeline_jobs.find().sort("started_at", -1).limit(limit)
    for job in await cursor.to_list(length=limit):
        sid = job.get("session_id")
        if sid:
            streams[ctl_stream(sid)] = "0-0"
    return streams


def _pipeline_envelope(entry_id: str, fields: dict[str, str]) -> dict:
    msg = envelope(entry_id, fields)
    event_type = msg.get("event_type", "")
    if event_type in PIPELINE_EVENT_TYPES:
        msg["channel"] = "pipeline"
    return msg


def _flatten_xread(batches: Any) -> list[tuple[str, str, dict[str, str]]]:
    out: list[tuple[str, str, dict[str, str]]] = []
    if not batches or not isinstance(batches, (list, tuple)):
        return out
    for batch in batches:
        if not isinstance(batch, (list, tuple)) or len(batch) < 2:
            continue
        stream_name = stream_id(batch[0])
        for entry_id, fields in xread_messages([batch]):
            out.append((stream_name, entry_id, ctl_fields(fields)))
    return out


@router.websocket("/ws/pipeline")
async def pipeline_ws(ws: WebSocket) -> None:
    await ws.accept()
    redis = await get_redis()
    cursors = await _active_session_streams()

    while True:
        try:
            if not cursors:
                if not await send_event(ws, {"channel": "pipeline", "event_type": "heartbeat", "data": {}}):
                    break
                await asyncio.sleep(WS_BLOCK_MS / 1000)
                cursors = await _active_session_streams()
                continue

            batches = await redis.xread(xread_streams(cursors), block=WS_BLOCK_MS, count=50)
            for stream_name, entry_id, fields in _flatten_xread(batches):
                msg = _pipeline_envelope(entry_id, fields)
                if msg.get("event_type") in PIPELINE_EVENT_TYPES:
                    if not await send_event(ws, msg):
                        return
                cursors[stream_name] = entry_id
        except Exception as exc:
            logger.warning("WS pipeline error: %s", exc)
            break
