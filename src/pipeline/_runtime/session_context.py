"""Resolve session coin/timeframe từ Redis — dùng filter pipeline theo yêu cầu user."""

from __future__ import annotations

from typing import Any

import redis.asyncio as aioredis

from src.pipeline._runtime.keys import state_key


def _decode(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def _state_get(state: dict[Any, Any], key: str) -> str:
    for k in (key, key.encode()):
        if k in state:
            return _decode(state[k])
    return ""


async def get_session_context(
    redis: aioredis.Redis,
    session_id: str,
) -> dict[str, str] | None:
    """Trả {coin_id, timeframe} hoặc None nếu không có state."""
    if not session_id:
        return None
    state = await redis.hgetall(state_key(session_id))
    if not state:
        return None
    coin = _state_get(state, "coin_id").upper()
    if not coin:
        return None
    timeframe = _state_get(state, "timeframe") or "1h"
    return {"coin_id": coin, "timeframe": timeframe}


def coin_matches(doc_coin: str | None, target_coin: str) -> bool:
    return str(doc_coin or "").upper() == str(target_coin).upper()
