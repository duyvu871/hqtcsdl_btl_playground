"""REST routes — analysis sessions, messages, PDF, signal."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import Response
from pydantic import BaseModel, Field

from src.api.services.pdf_export import generate_pdf
from src.api.services.session_monitor import spawn_session_monitor
from src.api.utils import strip_mongo_id
from src.common.mongo_client import get_db
from src.common.redis_client import get_redis
from src.orchestrator.session import create_session
from src.pipeline._runtime.keys import state_key

router = APIRouter(tags=["analysis"])


class CreateSessionRequest(BaseModel):
    coin_id: str = "BTC"
    timeframe: str = "1h"
    sources: list[str] | None = None


class FollowUpMessageRequest(BaseModel):
    content: str = Field(..., min_length=1)


@router.get("/analysis/sessions")
async def list_sessions(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
) -> dict:
    db = await get_db()
    cursor = db.analysis_sessions.find().sort("created_at", -1).skip(offset).limit(limit)
    sessions = [strip_mongo_id(doc) async for doc in cursor]
    return {"sessions": sessions, "limit": limit, "offset": offset}


@router.post("/analysis/sessions", status_code=201)
async def post_create_session(body: CreateSessionRequest) -> dict:
    coin = body.coin_id.upper()
    result = await create_session(
        coin,
        body.timeframe,
        sources=body.sources,
        user_message=f"Phân tích {coin} khung {body.timeframe}",
    )
    spawn_session_monitor(result["session_id"], result["job_id"])
    return {"session_id": result["session_id"], "job_id": result["job_id"]}


@router.get("/analysis/sessions/{session_id}")
async def get_session(session_id: str) -> dict:
    db = await get_db()
    session = await db.analysis_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    redis = await get_redis()
    state = await redis.hgetall(state_key(session_id))
    return {
        "session": strip_mongo_id(session),
        "state": state,
    }


@router.get("/analysis/sessions/{session_id}/messages")
async def get_session_messages(session_id: str) -> dict:
    db = await get_db()
    exists = await db.analysis_sessions.find_one({"session_id": session_id}, {"_id": 1})
    if not exists:
        raise HTTPException(status_code=404, detail="Session not found")

    cursor = db.chat_messages.find({"session_id": session_id}).sort("created_at", 1)
    messages = [strip_mongo_id(doc) async for doc in cursor]
    return {"messages": messages}


@router.post("/analysis/sessions/{session_id}/messages", status_code=201)
async def post_session_message(session_id: str, body: FollowUpMessageRequest) -> dict:
    db = await get_db()
    session = await db.analysis_sessions.find_one({"session_id": session_id})
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    message_id = str(uuid.uuid4())
    now = datetime.now(timezone.utc)
    await db.chat_messages.insert_one({
        "message_id": message_id,
        "session_id": session_id,
        "role": "user",
        "type": "user",
        "content": body.content,
        "metadata": {},
        "created_at": now,
    })
    return {"message_id": message_id}


@router.get("/analysis/sessions/{session_id}/export/pdf")
async def export_session_pdf(session_id: str) -> Response:
    try:
        pdf_bytes = await generate_pdf(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="report-{session_id}.pdf"'},
    )


@router.get("/coins/{coin_id}/signal")
async def get_coin_signal(
    coin_id: str,
    timeframe: str = Query("1h"),
) -> dict[str, Any]:
    db = await get_db()
    signal = await db.scoring_signals.find_one(
        {"coin_id": coin_id.upper()},
        sort=[("timestamp", -1)],
    )
    if not signal:
        raise HTTPException(status_code=404, detail=f"No signal for {coin_id}")

    doc = strip_mongo_id(signal) or {}
    doc["coin_id"] = coin_id.upper()
    doc["timeframe"] = timeframe
    return doc
