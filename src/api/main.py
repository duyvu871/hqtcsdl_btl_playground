"""FastAPI application — REST + WebSocket."""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes.analysis import router as analysis_router
from src.api.routes.market import router as market_router
from src.api.routes.pipeline import router as pipeline_router
from src.api.ws.analysis import router as ws_analysis_router
from src.api.ws.pipeline import router as ws_pipeline_router
from src.pipeline._runtime.keys import STAGE_ORDER

logger = logging.getLogger(__name__)


# Collections chứa dữ liệu pipeline — xóa toàn bộ documents khi startup
# (indexes + validators được giữ nguyên)
_PIPELINE_COLLECTIONS = [
    "raw_events",
    "clean_events",
    "dropped_events",
    "mapped_events",
    "sentiment_events",
    "sentiment_aggregates",
    "weighted_events",
    "influence_aggregates",
    "scoring_signals",
    "analysis_reports",
    "analysis_sessions",
    "chat_messages",
    "pipeline_jobs",
    "pipeline_stage_runs",
]


async def _flush_on_startup() -> None:
    """Xóa toàn bộ dữ liệu Redis + MongoDB khi server khởi động lại."""
    # 1. Redis ----------------------------------------------------------------
    try:
        from src.common.redis_client import get_redis

        redis = await get_redis()
        patterns = [
            "session:*:events",
            "session:*:state",
            "cursor:orch:*",
            "cursor:ws:*",
            *[f"stage:{s}:in" for s in STAGE_ORDER],
            *[f"stage:{s}:dlq" for s in STAGE_ORDER],
        ]
        redis_total = 0
        for pattern in patterns:
            keys = [k if isinstance(k, str) else k.decode() for k in await redis.keys(pattern)]
            if keys:
                await redis.delete(*keys)
                redis_total += len(keys)
        logger.info("Redis flush: %d keys removed.", redis_total)
    except Exception as exc:
        logger.warning("Redis flush skipped: %s", exc)

    # 2. MongoDB --------------------------------------------------------------
    try:
        from src.common.mongo_client import get_db

        db = await get_db()
        mongo_total = 0
        for col in _PIPELINE_COLLECTIONS:
            result = await db[col].delete_many({})
            if result.deleted_count:
                logger.info("  %-28s: %d docs removed", col, result.deleted_count)
            mongo_total += result.deleted_count
        logger.info("MongoDB flush: %d documents removed.", mongo_total)
    except Exception as exc:
        logger.warning("MongoDB flush skipped: %s", exc)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info("=== Server startup: flushing all session data ===")
    await _flush_on_startup()
    yield
    logger.info("=== Server shutdown ===")


app = FastAPI(
    title="Crypto Social Intelligence API",
    version="0.1.0",
    description="REST + WebSocket cho dashboard, chat phân tích và ETL monitor.",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(market_router, prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(ws_analysis_router)
app.include_router(ws_pipeline_router)


@app.get("/")
async def root() -> dict[str, str]:
    return {"service": "crypto-social-intelligence", "docs": "/docs"}
