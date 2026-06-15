"""Kiểm tra Insight stage (Phase 7) — unit + integration, MongoDB + Redis.

Chạy: uv run pytest tests/test_insight.py -v
Cần: docker compose (MongoDB + Redis).

Danh sách test:
  test_t7_01_llm_token_stream_order     — T7-01 llm_token emit đúng thứ tự
  test_t7_02_analysis_report_fields     — T7-02 analysis_reports đủ field
  test_t7_03_report_done_emit           — T7-03 report_done trên control stream
  test_t7_04_chat_message_report        — T7-04 chat_messages type=report
  test_t7_05_llm_fallback               — T7-05 llm_fallback khi LLM lỗi
  test_t7_08_session_completed          — T7-08 report_done → session completed
"""

from __future__ import annotations

import json
import sys
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.common.mongo_client import close_mongo, get_db
from src.common.redis_client import close_redis, get_redis
from src.orchestrator.monitor import drain_control_events
from src.pipeline._runtime.keys import ctl_stream
from src.pipeline.insight.documents import parse_report_text
from src.pipeline.insight.prompt import render_prompt
from src.pipeline.insight.service import reset_insight_pipeline
from src.pipeline.insight.worker import insight_processor

TEST_DB = "crypto_mvp_test"


def _signal(**extra) -> dict:
    base = {
        "signal_id": f"sig-{uuid.uuid4().hex[:8]}",
        "coin_id": "BTC",
        "timeframe": "1h",
        "action": "BUY",
        "metrics": {
            "galaxy_alpha_score": 68.2,
            "galaxy_safety_score": 55.1,
            "confidence": 72.5,
        },
        "execution": {"target_price": 70000.0, "stop_loss": 65000.0},
        "timestamp": int(datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc).timestamp()),
    }
    base.update(extra)
    return base


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


@pytest.mark.asyncio
async def test_t7_01_llm_token_stream_order(test_db, redis_client, monkeypatch) -> None:
    """T7-01: mock stream → llm_token events đúng thứ tự."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    tokens = ["Xin ", "chào ", "BTC"]

    async def _mock_collect(prompt, *, redis, session_id, job_id="", model=None):
        from src.pipeline._runtime.emit import emit

        for token in tokens:
            await emit(redis, session_id, "llm_token", {"token": token}, job_id=job_id)
        return "".join(tokens), "mock-model"

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_collect)

    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    })

    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": "job-t7"})

    entries = await redis_client.xrange(ctl_stream(session_id))
    llm_events = [f for _, f in entries if f.get("event_type") == "llm_token"]
    received = [json.loads(e["data"])["token"] for e in llm_events]
    assert received == tokens


@pytest.mark.asyncio
async def test_t7_02_analysis_report_fields(test_db, redis_client, monkeypatch) -> None:
    """T7-02: analysis_reports có đủ field required."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"

    async def _mock_collect(*_a, **_kw):
        text = (
            "Tóm tắt tín hiệu BUY cho BTC.\n\n"
            "Key findings:\n- Volume tăng\n- Sentiment dương\n\n"
            "Risk factors:\n- Biến động cao\n\n"
            "Recommendation: Theo dõi thận trọng.\n"
        )
        return text, "mock-model"

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_collect)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    })

    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": "job-t7"})

    report = await test_db.analysis_reports.find_one({"session_id": session_id})
    assert report is not None
    for field in ("report_id", "session_id", "coin_id", "summary", "generated_at"):
        assert report.get(field) is not None
    assert report.get("sections", {}).get("full_text")


@pytest.mark.asyncio
async def test_t7_03_report_done_emit(test_db, redis_client, monkeypatch) -> None:
    """T7-03: control stream có report_done với report_id."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"

    async def _mock_collect(*_a, **_kw):
        return "Report done.", "mock-model"

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_collect)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    })

    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": "job-t7"})

    entries = await redis_client.xrange(ctl_stream(session_id))
    done = [f for _, f in entries if f.get("event_type") == "report_done"]
    assert len(done) == 1
    data = json.loads(done[0]["data"])
    assert data.get("report_id")


@pytest.mark.asyncio
async def test_t7_04_chat_message_report(test_db, redis_client, monkeypatch) -> None:
    """T7-04: chat_messages type=report với full markdown."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    full = "# BTC Report\n\nNội dung báo cáo đầy đủ."

    async def _mock_collect(*_a, **_kw):
        return full, "mock-model"

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_collect)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    })

    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": "job-t7"})

    msg = await test_db.chat_messages.find_one({"session_id": session_id, "type": "report"})
    assert msg is not None
    assert msg["content"] == full
    assert msg["metadata"].get("report_id")


@pytest.mark.asyncio
async def test_t7_05_llm_fallback(test_db, redis_client, monkeypatch) -> None:
    """T7-05: LLM lỗi → llm_fallback=true, report vẫn ghi."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"

    async def _mock_fail(*_a, **_kw):
        raise RuntimeError("LLM down")

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_fail)
    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "status": "running",
        "created_at": datetime.now(timezone.utc),
    })

    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": "job-t7"})

    report = await test_db.analysis_reports.find_one({"session_id": session_id})
    assert report is not None
    assert report["sections"]["llm_fallback"] is True
    assert "LLM unavailable" in report["sections"]["full_text"]


@pytest.mark.asyncio
async def test_t7_08_session_completed(test_db, redis_client, monkeypatch) -> None:
    """T7-08: orchestrator nhận report_done → analysis_sessions completed."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-t7-08"
    now = datetime.now(timezone.utc)

    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "job_id": job_id,
        "status": "running",
        "created_at": now,
    })
    await test_db.pipeline_jobs.insert_one({
        "job_id": job_id,
        "session_id": session_id,
        "status": "running",
        "started_at": now,
    })

    async def _mock_collect(*_a, **_kw):
        return "Done.", "mock-model"

    monkeypatch.setattr("src.pipeline.insight.service.collect_insight_text", _mock_collect)
    reset_insight_pipeline()
    await insight_processor(_signal(), {"session_id": session_id, "job_id": job_id})

    status = await drain_control_events(session_id, job_id, redis=redis_client)
    assert status == "completed"

    session = await test_db.analysis_sessions.find_one({"session_id": session_id})
    assert session["status"] == "completed"


def test_parse_report_text_bullets() -> None:
    text = "Summary line.\n\n- Point A\n- Point B\n\nRisk factors:\n- Risk 1\n"
    parsed = parse_report_text(text)
    assert parsed["summary"]
    assert len(parsed["key_findings"]) >= 1


def test_render_prompt_has_coin() -> None:
    prompt = render_prompt({
        "coin_id": "ETH",
        "timeframe": "4h",
        "alpha": 60,
        "safety": 50,
        "action": "HOLD",
        "confidence": 80,
        "social_volume": 100,
        "weighted_sentiment": 0.3,
        "top_events": [],
    })
    assert "ETH" in prompt
