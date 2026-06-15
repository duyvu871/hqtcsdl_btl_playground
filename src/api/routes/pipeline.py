"""REST routes — pipeline monitor + health."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Response
from pydantic import BaseModel, Field

from src.api.services.session_monitor import spawn_session_monitor
from src.api.utils import strip_mongo_id
from src.common.mongo_client import get_db, mongo_ping
from src.common.redis_client import get_redis, redis_ping
from src.orchestrator.session import build_kickoff_payload, create_session, new_job_id
from src.pipeline._runtime.keys import STAGE_ORDER
from src.pipeline._runtime.worker import publish_entry

router = APIRouter(tags=["pipeline"])

STATS_COLLECTIONS = [
    "raw_events",
    "clean_events",
    "dropped_events",
    "mapped_events",
    "sentiment_events",
    "weighted_events",
    "influence_aggregates",
    "scoring_signals",
    "analysis_reports",
    "chat_messages",
]


class PipelineRunRequest(BaseModel):
    coin_id: str = "BTC"
    timeframe: str = "1h"
    session_id: str | None = None
    stages: list[str] = Field(default_factory=lambda: list(STAGE_ORDER))
    dry_run: bool = False
    sources: list[str] | None = None


@router.get("/health")
async def health_check() -> Response:
    mongo_status = "ok"
    redis_status = "ok"
    try:
        await mongo_ping()
    except Exception:
        mongo_status = "error"
    try:
        if not await redis_ping():
            redis_status = "error"
    except Exception:
        redis_status = "error"

    from fastapi.responses import JSONResponse

    body = {"mongodb": mongo_status, "redis": redis_status, "api": "ok", "workers": "unknown"}
    status_code = 200 if mongo_status == "ok" and redis_status == "ok" else 503
    return JSONResponse(status_code=status_code, content=body)


@router.post("/pipeline/run")
async def pipeline_run(body: PipelineRunRequest) -> dict[str, str]:
    if body.dry_run:
        return {"job_id": new_job_id(), "status": "dry_run"}

    if body.session_id:
        db = await get_db()
        session = await db.analysis_sessions.find_one({"session_id": body.session_id})
        if not session:
            raise HTTPException(status_code=404, detail="Session not found")
        job_id = session.get("job_id", new_job_id())
        session_id = body.session_id
        coin = session.get("coin_id", body.coin_id).upper()
        timeframe = session.get("timeframe", body.timeframe)
        kickoff = build_kickoff_payload(coin, timeframe, sources=body.sources)
        redis = await get_redis()
        import uuid

        await publish_entry(
            redis,
            "ingest",
            kickoff,
            session_id=session_id,
            job_id=job_id,
            trace_id=str(uuid.uuid4()),
            produced_by="api:pipeline/run",
        )
        spawn_session_monitor(session_id, job_id)
        return {"job_id": job_id, "status": "running", "session_id": session_id}

    result = await create_session(
        body.coin_id,
        body.timeframe,
        sources=body.sources,
        user_message=f"Pipeline run {body.coin_id.upper()} {body.timeframe}",
    )
    spawn_session_monitor(result["session_id"], result["job_id"])
    return {
        "job_id": result["job_id"],
        "status": "running",
        "session_id": result["session_id"],
    }


@router.get("/pipeline/jobs")
async def list_pipeline_jobs(
    limit: int = Query(20, ge=1, le=100),
    status: str | None = Query(None),
) -> dict:
    db = await get_db()
    query: dict[str, Any] = {}
    if status:
        query["status"] = status
    cursor = db.pipeline_jobs.find(query).sort("started_at", -1).limit(limit)
    jobs = [strip_mongo_id(doc) async for doc in cursor]
    return {"jobs": jobs}


@router.get("/pipeline/jobs/{job_id}")
async def get_pipeline_job(job_id: str) -> dict:
    db = await get_db()
    job = await db.pipeline_jobs.find_one({"job_id": job_id})
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    stages = await db.pipeline_stage_runs.find({"job_id": job_id}).sort("stage", 1).to_list(20)
    return {
        "job": strip_mongo_id(job),
        "stages": [strip_mongo_id(s) for s in stages],
    }


@router.get("/pipeline/stats")
async def pipeline_stats() -> dict[str, int]:
    db = await get_db()
    stats: dict[str, int] = {}
    for name in STATS_COLLECTIONS:
        stats[name] = await db[name].count_documents({})
    return stats
