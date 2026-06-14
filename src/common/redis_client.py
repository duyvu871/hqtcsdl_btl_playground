"""Async Redis client singleton."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from src.common.config import settings

_redis: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Return shared async Redis connection (lazy init)."""
    global _redis
    if _redis is None:
        _redis = aioredis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
            socket_connect_timeout=3,
        )
    return _redis


async def close_redis() -> None:
    """Close Redis connection (for tests / shutdown)."""
    global _redis
    if _redis is not None:
        await _redis.aclose()
        _redis = None


async def redis_ping() -> bool:
    """Health check helper."""
    client = await get_redis()
    return bool(await client.ping())


def stream_entry_id(entry_id: str | bytes) -> str:
    """Chuẩn hóa ID từ XADD — stub redis trả bytes|str, client dùng decode_responses=True."""
    return entry_id if isinstance(entry_id, str) else entry_id.decode()


async def xadd(
    stream: str,
    fields: dict[str, Any],
    *,
    maxlen: int | None = None,
    approximate: bool = True,
) -> str:
    """XADD wrapper with optional MAXLEN."""
    client = await get_redis()
    kwargs: dict[str, Any] = {}
    if maxlen is not None:
        kwargs["maxlen"] = maxlen
        kwargs["approximate"] = approximate
    return stream_entry_id(await client.xadd(stream, fields, **kwargs))
