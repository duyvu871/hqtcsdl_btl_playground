"""Planning phase — emit 7 planning_step vào control stream + chat_messages."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

import redis.asyncio as aioredis

from src.common.mongo_client import get_db
from src.pipeline._runtime.emit import emit

PLANNING_STEPS: list[tuple[str, str]] = [
    ("Ingest", "Thu thập dữ liệu social từ Twitter, Alpha Vantage, Yahoo Finance"),
    ("Filter", "Lọc spam và nhiễu (cascade L1/L2/L3)"),
    ("NER", "Nhận diện và gán mã coin từ nội dung"),
    ("Sentiment", "Phân tích cảm xúc thị trường qua FinBERT"),
    ("Influence", "Đo trọng số ảnh hưởng và aggregate theo cửa sổ thời gian"),
    ("Scoring", "Tính Galaxy Alpha/Safety Score và xác định tín hiệu BUY/HOLD"),
    ("Insight", "Tổng hợp báo cáo phân tích bằng LLM và xuất PDF"),
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


async def emit_planning(
    redis: aioredis.Redis,
    session_id: str,
    *,
    job_id: str = "",
) -> list[dict[str, Any]]:
    """Emit 7 planning_step + mirror vào chat_messages. Trả list message docs."""
    db = await get_db()
    messages: list[dict[str, Any]] = []

    for i, (stage, desc) in enumerate(PLANNING_STEPS, 1):
        await emit(
            redis,
            session_id,
            "planning_step",
            {"step": i, "stage": stage.lower(), "description": desc},
            job_id=job_id,
        )
        doc: dict[str, Any] = {
            "message_id": str(uuid.uuid4()),
            "session_id": session_id,
            "role": "assistant",
            "type": "planning",
            "content": f"{i}. {stage} — {desc}",
            "metadata": {"step": i, "stage": stage.lower()},
            "created_at": utcnow(),
        }
        await db.chat_messages.insert_one(doc)
        messages.append(doc)

    return messages
