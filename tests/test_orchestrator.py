"""Kiểm tra Orchestrator (Phase 6) — session, planning, state machine, finalize.

Chạy: uv run pytest tests/test_orchestrator.py -v
Cần: docker compose (MongoDB + Redis).

Danh sách test:
  test_t6_01_create_session_running       — T6-01 created → running sau kickoff
  test_t6_02_scoring_to_insight_streaming — T6-02 stage_completed scoring → insight_streaming
  test_t6_03_stage_failed_partial       — T6-03 stage_failed → failed_partial
  test_t6_04_planning_steps_emit        — T6-04 7 planning_step trên control stream
  test_t6_05_planning_chat_messages     — T6-05 7 chat_messages type=planning
  test_t6_06_e2e_through_scoring        — T6-06 pipeline drain Stage 1→6
  test_t6_07_finalize_snapshot          — T6-07 pipeline_stage_runs 6 docs
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.common.mongo_client import close_mongo, get_db
from src.common.redis_client import close_redis, get_redis
from src.orchestrator.monitor import drain_control_events, finalize_session, handle_control_event
from src.orchestrator.planning import PLANNING_STEPS
from src.orchestrator.session import create_session
from src.pipeline._persist import upsert_market_ohlcv
from src.pipeline._runtime.emit import emit
from src.pipeline._runtime.keys import ctl_stream, in_stream, state_key
from src.pipeline._runtime.worker import process_batch
from src.pipeline.filter.service import reset_filter_pipeline
from src.pipeline.filter.worker import filter_processor
from src.pipeline.influence.service import reset_influence_pipeline
from src.pipeline.influence.worker import influence_processor
from src.pipeline.ingest.worker import ingest_processor
from src.pipeline.ner.service import reset_ner_pipeline
from src.pipeline.ner.worker import ner_processor
from src.pipeline.scoring.mock_data import get_mock_scenario
from src.pipeline.scoring.service import reset_scoring_pipeline
from src.pipeline.sentiment.service import reset_sentiment_pipeline
from src.pipeline.sentiment.worker import sentiment_processor

TEST_DB = "crypto_mvp_test"


@pytest.fixture
async def test_db(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr("src.common.config.settings.MONGODB_DB", TEST_DB)
    await close_mongo()
    try:
        db = await get_db()
        from src.common.schema import bootstrap_indexes

        await bootstrap_indexes(db)
        yield db
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    finally:
        try:
            db = await get_db()
            await db.client.drop_database(TEST_DB)
        except Exception:
            pass
        await close_mongo()


@pytest.fixture
async def redis_client():
    try:
        redis = await get_redis()
        yield redis
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")
    finally:
        await close_redis()


def _synthetic_raw(coin_id: str = "BTC") -> dict:
    from src.pipeline.ingest.events import _base_event

    return _base_event(
        source="twitter",
        raw_text=f"Federal Reserve holds rates steady, ${coin_id} consolidates",
        author_id="orch-test",
        metrics={"followers": 50_000, "likes": 120, "retweets": 30, "verified": True},
        timestamp=int(datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc).timestamp()),
    )


async def _seed_ohlcv() -> None:
    raw = get_mock_scenario("bullish_divergence", rows=48)
    candles = [
        {"timestamp": ts, "close": close, "volume": vol}
        for ts, close, vol in zip(raw["timestamp"], raw["close"], raw["volume"])
    ]
    await upsert_market_ohlcv("BTC", "1h", candles)


@pytest.mark.asyncio
async def test_t6_01_create_session_running(test_db, redis_client) -> None:
    result = await create_session("BTC", "1h", sources=[], user_message="Phân tích BTC")
    session_id = result["session_id"]

    state = await redis_client.hgetall(state_key(session_id))
    assert state.get("status") == "running"
    assert state.get("coin_id") == "BTC"
    assert await redis_client.xlen(in_stream("ingest")) >= 1

    session = await test_db.analysis_sessions.find_one({"session_id": session_id})
    assert session is not None
    assert session["status"] == "running"


@pytest.mark.asyncio
async def test_t6_02_scoring_to_insight_streaming(test_db, redis_client) -> None:
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-t6-02"
    await redis_client.hset(state_key(session_id), mapping={"status": "running", "job_id": job_id})

    status = await handle_control_event(
        redis_client, session_id, job_id,
        "stage_completed", {"stage": "scoring", "records_in": 1, "records_out": 1},
    )
    assert status == "insight_streaming"
    state = await redis_client.hgetall(state_key(session_id))
    assert state.get("status") == "insight_streaming"


@pytest.mark.asyncio
async def test_t6_03_stage_failed_partial(test_db, redis_client) -> None:
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-t6-03"
    now = datetime.now(timezone.utc)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id, "coin_id": "BTC", "timeframe": "1h",
        "job_id": job_id, "status": "running", "created_at": now,
    })
    await test_db.pipeline_jobs.insert_one({
        "job_id": job_id, "session_id": session_id, "status": "running", "started_at": now,
    })
    await redis_client.hset(state_key(session_id), mapping={"status": "running", "job_id": job_id})

    status = await handle_control_event(
        redis_client, session_id, job_id,
        "stage_failed", {"stage": "filter", "error": "simulated"},
    )
    assert status == "failed_partial"
    session = await test_db.analysis_sessions.find_one({"session_id": session_id})
    assert session["status"] == "failed"


@pytest.mark.asyncio
async def test_t6_04_planning_steps_emit(test_db, redis_client) -> None:
    result = await create_session("ETH", "1h", sources=[])
    entries = await redis_client.xrange(ctl_stream(result["session_id"]))
    planning = [f for _, f in entries if f.get("event_type") == "planning_step"]
    assert len(planning) == len(PLANNING_STEPS)


@pytest.mark.asyncio
async def test_t6_05_planning_chat_messages(test_db, redis_client) -> None:
    result = await create_session("SOL", "4h", sources=[], user_message="Analyze SOL")
    session_id = result["session_id"]
    assert await test_db.chat_messages.count_documents({"session_id": session_id, "type": "planning"}) == 7
    assert await test_db.chat_messages.count_documents({"session_id": session_id, "type": "user"}) == 1


@pytest.mark.asyncio
async def test_t6_07_finalize_snapshot(test_db, redis_client) -> None:
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-t6-07"
    now = datetime.now(timezone.utc)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id, "coin_id": "BTC", "timeframe": "1h",
        "job_id": job_id, "status": "running", "created_at": now,
    })
    await test_db.pipeline_jobs.insert_one({
        "job_id": job_id, "session_id": session_id, "status": "running", "started_at": now,
    })
    await redis_client.hset(state_key(session_id), mapping={
        "status": "running", "job_id": job_id, "scoring_out": "1",
    })

    await finalize_session(session_id, job_id, through_stage="scoring")
    runs = await test_db.pipeline_stage_runs.find({"job_id": job_id}).to_list(10)
    assert len(runs) == 6
    assert {r["stage"] for r in runs} == {
        "ingest", "filter", "ner", "sentiment", "influence", "scoring",
    }


@pytest.mark.asyncio
async def test_t6_06_e2e_through_scoring(test_db, redis_client, monkeypatch) -> None:
    def _fake_collect(payload: dict):
        doc = _synthetic_raw(str(payload.get("coin_id", "BTC")))
        doc["event_id"] = f"raw-{uuid.uuid4().hex[:8]}"
        return [doc]

    monkeypatch.setattr("src.pipeline.ingest.worker.collect_from_kickoff", _fake_collect)

    for stage in ("ingest", "filter", "ner", "sentiment", "influence", "scoring"):
        await redis_client.delete(in_stream(stage))

    reset_filter_pipeline()
    reset_ner_pipeline()
    reset_sentiment_pipeline()
    reset_influence_pipeline()
    reset_scoring_pipeline()

    result = await create_session("BTC", "1h", sources=["twitter"])
    session_id = result["session_id"]
    job_id = result["job_id"]

    processors = {
        "ingest": ingest_processor,
        "filter": filter_processor,
        "ner": ner_processor,
        "sentiment": sentiment_processor,
        "influence": influence_processor,
    }
    for stage, proc in processors.items():
        for _ in range(20):
            if await process_batch(redis_client, stage, proc, consumer=f"orch-{stage}", block_ms=200) == 0:
                break

    assert await test_db.weighted_events.count_documents({"coin_id": "BTC"}) >= 1

    await emit(redis_client, session_id, "stage_completed", {"stage": "scoring"}, job_id=job_id)
    assert await drain_control_events(session_id, job_id, redis=redis_client) == "insight_streaming"
    assert (await redis_client.hget(state_key(session_id), "status")) == "insight_streaming"

    runs = await test_db.pipeline_stage_runs.find({"job_id": job_id}).to_list(10)
    assert len(runs) == 6
