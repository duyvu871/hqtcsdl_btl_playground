"""Spawn orchestrator monitor — fire-and-forget, không block HTTP response."""

from __future__ import annotations

import asyncio
import logging

from src.orchestrator.monitor import monitor_session

logger = logging.getLogger(__name__)

_active_monitors: dict[str, asyncio.Task[None]] = {}


def spawn_session_monitor(session_id: str, job_id: str) -> None:
    """
    Chạy monitor_session nền — detached khỏi Starlette BackgroundTasks.

    BackgroundTasks await coroutine → block HTTP + bị cancel khi request kết thúc.
    asyncio.create_task giữ monitor sống độc lập với request lifecycle.
    """
    existing = _active_monitors.get(session_id)
    if existing is not None and not existing.done():
        logger.debug("Monitor already running for session %s", session_id)
        return

    async def _run() -> None:
        try:
            status = await monitor_session(session_id, job_id)
            logger.info("Session %s monitor finished: %s", session_id, status)
        except asyncio.CancelledError:
            logger.info("Session %s monitor cancelled", session_id)
            raise
        except Exception:
            logger.exception("Session %s monitor error", session_id)
        finally:
            _active_monitors.pop(session_id, None)

    task = asyncio.create_task(_run(), name=f"monitor:{session_id[:8]}")
    _active_monitors[session_id] = task
