"""WebSocket /ws/analysis/{session_id} — catch-up + live."""

from __future__ import annotations

import logging

from fastapi import APIRouter, WebSocket

from src.common.redis_client import get_redis
from src.pipeline._runtime.keys import ctl_stream
from src.api.ws._helpers import (
    envelope,
    send_event,
    stream_id,
    xrange_messages,
    xread_messages,
    xread_streams,
)

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])

WS_BLOCK_MS = 2_000


@router.websocket("/ws/analysis/{session_id}")
async def analysis_ws(ws: WebSocket, session_id: str, last_id: str = "0") -> None:
    await ws.accept()
    redis = await get_redis()
    stream = ctl_stream(session_id)
    cursor = stream_id(last_id) if last_id and last_id != "0" else "0-0"

    # Phase 1: catch-up
    start = f"({cursor}" if cursor != "0-0" else "-"
    entries = await redis.xrange(stream, min=start, max="+")
    for entry_id, fields in xrange_messages(entries):
        if not await send_event(ws, envelope(entry_id, fields)):
            logger.debug("WS analysis catch-up disconnect session=%s", session_id)
            return
        cursor = entry_id

    # Phase 2: live loop
    while True:
        try:
            batches = await redis.xread(xread_streams({stream: cursor}), block=WS_BLOCK_MS, count=50)
        except Exception as exc:
            logger.warning("WS analysis redis error session=%s: %s", session_id, exc)
            break

        for entry_id, fields in xread_messages(batches):
            if not await send_event(ws, envelope(entry_id, fields)):
                logger.debug("WS analysis live disconnect session=%s", session_id)
                return
            cursor = entry_id
