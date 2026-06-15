"""Kiểm tra Influence + Scoring tích hợp (Phase 5) — MongoDB + Redis stream.

Chạy: uv run pytest tests/test_influence_scoring_integration.py -v
Cần: docker compose (MongoDB + Redis).

Danh sách test:
  test_t5_03_batch_trigger_to_scoring  — influence → stage:scoring:in
  test_t5_04_signal_ready_emit           — scoring emit signal_ready
  test_stream_sentiment_to_signal        — sentiment → influence → scoring (mock OHLCV)
"""

from __future__ import annotations

import json
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
from src.pipeline._persist import upsert_market_ohlcv
from src.pipeline._runtime.keys import ctl_stream, in_stream
from src.pipeline._runtime.worker import pending_count, process_batch, publish_entry
from src.pipeline.influence.service import reset_influence_pipeline
from src.pipeline.influence.worker import influence_processor
from src.pipeline.scoring.mock_data import get_mock_scenario
from src.pipeline.scoring.service import reset_scoring_pipeline
from src.pipeline.scoring.worker import scoring_processor
from src.pipeline.sentiment.documents import build_sentiment_event
from src.pipeline.sentiment.rule_based import rule_based_score

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


def _sentiment_doc(**extra) -> dict:
    mapped = {
        "mapped_id": f"map-{uuid.uuid4().hex[:8]}",
        "parent_event_id": f"clean-{uuid.uuid4().hex[:8]}",
        "event_id": f"clean-{uuid.uuid4().hex[:8]}",
        "coin_id": "BTC",
        "source": "twitter",
        "clean_text": "Federal Reserve holds rates steady, BTC steady",
        "author_id": "analyst-1",
        "timestamp": int(datetime(2026, 6, 14, 12, 0, tzinfo=timezone.utc).timestamp()),
        "filter": {"stage": "passed"},
        "ner": {"method": "cashtag", "confidence": 0.9},
        "metrics": {"followers": 500_000, "likes": 200, "retweets": 50, "verified": True},
    }
    mapped.update(extra)
    score = rule_based_score(mapped["clean_text"])
    doc = build_sentiment_event(mapped, score)
    doc["sentiment_id"] = f"sent-{uuid.uuid4().hex[:8]}"
    return doc


async def _seed_ohlcv(coin_id: str = "BTC", timeframe: str = "1h") -> None:
    raw = get_mock_scenario("bullish_divergence", rows=48)
    candles = [
        {"timestamp": ts, "close": close, "volume": vol}
        for ts, close, vol in zip(raw["timestamp"], raw["close"], raw["volume"])
    ]
    await upsert_market_ohlcv(coin_id, timeframe, candles)


@pytest.mark.asyncio
async def test_t5_03_batch_trigger_to_scoring(test_db, redis_client) -> None:
    """Influence worker emit entry lên stage:scoring:in."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    sentiment = _sentiment_doc()

    for key in (in_stream("influence"), in_stream("scoring")):
        await redis_client.delete(key)

    reset_influence_pipeline()

    await publish_entry(
        redis_client,
        "influence",
        sentiment,
        session_id=session_id,
        job_id="job-t5",
        trace_id=str(uuid.uuid4()),
        produced_by="stage:sentiment",
    )

    processed = await process_batch(
        redis_client,
        "influence",
        influence_processor,
        consumer="inf-int-test",
        block_ms=1000,
    )
    assert processed == 1

    entries = await redis_client.xrange(in_stream("scoring"), count=5)
    assert len(entries) >= 1

    weighted_count = await test_db.weighted_events.count_documents({"coin_id": "BTC"})
    assert weighted_count == 1

    agg_count = await test_db.influence_aggregates.count_documents({"coin_id": "BTC"})
    assert agg_count >= 1


@pytest.mark.asyncio
async def test_t5_04_signal_ready_emit(test_db, redis_client) -> None:
    """Scoring hoàn tất → control stream có signal_ready."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    await _seed_ohlcv()

    raw = get_mock_scenario("bullish_divergence", rows=48)
    social_history = [
        {
            "timestamp": ts,
            "coin_id": "BTC",
            "sentiment_score": score,
            "social_volume": vol,
        }
        for ts, score, vol in zip(
            raw["timestamp"], raw["sentiment_score"], raw["social_volume"]
        )
    ]
    trigger = {
        "coin_id": "BTC",
        "timeframe": "1h",
        "aggregate": {
            "coin_id": "BTC",
            "timeframe": "1h",
            "sentiment_score": 0.5,
            "social_volume": 10,
        },
        "social_history": social_history,
    }

    await redis_client.delete(ctl_stream(session_id))
    await redis_client.delete(in_stream("scoring"))
    reset_scoring_pipeline()

    await publish_entry(
        redis_client,
        "scoring",
        trigger,
        session_id=session_id,
        job_id="job-t5-signal",
        trace_id=str(uuid.uuid4()),
        produced_by="stage:influence",
    )

    processed = await process_batch(
        redis_client,
        "scoring",
        scoring_processor,
        consumer="score-int-test",
        block_ms=1000,
    )
    assert processed == 1

    signals = await test_db.scoring_signals.count_documents({"coin_id": "BTC"})
    assert signals >= 1

    ctl_entries = await redis_client.xrange(ctl_stream(session_id), count=20)
    signal_events = [
        fields for _id, fields in ctl_entries if fields.get("event_type") == "signal_ready"
    ]
    assert len(signal_events) >= 1

    data = json.loads(signal_events[0]["data"])
    assert data["action"] in ("BUY", "HOLD", "SELL")
    assert "alpha" in data
    assert "safety" in data


@pytest.mark.asyncio
async def test_stream_sentiment_to_signal(test_db, redis_client) -> None:
    """sentiment → influence → scoring end-to-end (mock OHLCV cache)."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    await _seed_ohlcv()

    raw = get_mock_scenario("bullish_divergence", rows=48)

    for key in (in_stream("influence"), in_stream("scoring")):
        await redis_client.delete(key)
    await redis_client.delete(ctl_stream(session_id))

    reset_influence_pipeline()
    reset_scoring_pipeline()

    for i, (ts, score) in enumerate(zip(raw["timestamp"], raw["sentiment_score"])):
        sentiment = _sentiment_doc(
            timestamp=int(ts),
            clean_text=f"BTC market update row {i}",
        )
        sentiment["sentiment_score"] = float(score)
        sentiment["sentiment_id"] = f"sent-{uuid.uuid4().hex[:8]}"

        await publish_entry(
            redis_client,
            "influence",
            sentiment,
            session_id=session_id,
            job_id="job-e2e",
            trace_id=str(uuid.uuid4()),
            produced_by="stage:sentiment",
        )
        await process_batch(
            redis_client,
            "influence",
            influence_processor,
            consumer="e2e-inf",
            block_ms=500,
        )

    scoring_entries = await redis_client.xlen(in_stream("scoring"))
    assert scoring_entries >= 1

    await process_batch(
        redis_client,
        "scoring",
        scoring_processor,
        consumer="e2e-score",
        block_ms=1000,
    )
    assert await pending_count(redis_client, "scoring") == 0

    signal = await test_db.scoring_signals.find_one({"coin_id": "BTC"}, sort=[("timestamp", -1)])
    assert signal is not None
    assert signal["action"] in ("BUY", "HOLD", "SELL")
