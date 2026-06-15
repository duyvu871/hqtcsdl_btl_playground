"""WebSocket helpers — envelope + Redis stream parsing."""

from __future__ import annotations

import json
from typing import Any

from fastapi import WebSocket
from starlette.websockets import WebSocketDisconnect


def xread_streams(cursors: dict[str, str]) -> dict[Any, Any]:
    """Chuẩn hóa stream cursors cho redis.xread (redis-py TypeVar stubs)."""
    return cursors


def _as_str(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def ctl_fields(raw: Any) -> dict[str, str]:
    if not isinstance(raw, dict):
        return {}
    return {_as_str(k): _as_str(v) for k, v in raw.items()}


def stream_id(value: Any) -> str:
    if value is None:
        return "0-0"
    if isinstance(value, bytes):
        return value.decode()
    return str(value)


def xrange_messages(entries: Any) -> list[tuple[str, dict[str, str]]]:
    messages: list[tuple[str, dict[str, str]]] = []
    if not entries:
        return messages
    for item in entries:
        if not isinstance(item, (list, tuple)) or len(item) < 2:
            continue
        entry_id, fields = item[0], item[1]
        if fields is None:
            continue
        messages.append((stream_id(entry_id), ctl_fields(fields)))
    return messages


def xread_messages(entries: Any) -> list[tuple[str, dict[str, str]]]:
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
        messages.append((stream_id(entry_id), ctl_fields(fields)))
    return messages


def envelope(entry_id: str, fields: dict[str, str]) -> dict[str, Any]:
    raw_data = fields.get("data", "{}")
    try:
        data = json.loads(raw_data)
    except json.JSONDecodeError:
        data = {}
    return {
        "id": entry_id,
        "event_type": fields.get("event_type", ""),
        "session_id": fields.get("session_id", ""),
        "job_id": fields.get("job_id", ""),
        "data": data,
        "ts": fields.get("ts", ""),
    }


async def send_event(ws: WebSocket, payload: dict[str, Any]) -> bool:
    """Gửi JSON qua WS; trả False nếu client đã disconnect."""
    try:
        await ws.send_json(payload)
        return True
    except WebSocketDisconnect:
        return False

