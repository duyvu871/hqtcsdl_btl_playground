"""Kiểm tra NER + Sentiment tích hợp (Phase 4) — MongoDB + Redis stream.

Chạy: uv run pytest tests/test_ner_sentiment_integration.py -v
Cần: docker compose (MongoDB + Redis).

Danh sách test:
  test_t4_02_fanout_idempotent   — chạy NER 2 lần → không duplicate mapped_events
  test_t4_stream_filter_to_sentiment — clean → NER → sentiment qua Redis stream
"""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.common.mongo_client import close_mongo, get_db
from src.common.redis_client import close_redis, get_redis
from src.pipeline._persist import insert_mapped_event
from src.pipeline._runtime.keys import in_stream
from src.pipeline._runtime.worker import pending_count, process_batch, publish_entry
from src.pipeline.ner.service import reset_ner_pipeline
from src.pipeline.ner.worker import ner_processor
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


def _clean_doc(**extra) -> dict:
    base = {
        "event_id": f"clean-{uuid.uuid4().hex[:8]}",
        "source": "twitter",
        "clean_text": "Rotation from $BTC into $ETH looks likely",
        "raw_text": "Rotation from $BTC into $ETH looks likely",
        "author_id": "analyst-1",
        "metrics": {"likes": 100},
        "timestamp": 1_718_380_800,
        "is_spam": False,
        "filter": {"stage": "passed", "layers": ["heuristic"]},
        "filtered_at": 1_718_380_900,
    }
    base.update(extra)
    return base


@pytest.mark.asyncio
async def test_t4_02_fanout_idempotent(test_db) -> None:
    """Chạy insert mapped 2 lần → chỉ 1 doc per (parent, coin)."""
    clean = _clean_doc()
    reset_ner_pipeline()
    from src.pipeline.ner.service import get_ner_pipeline

    _, docs = get_ner_pipeline().process(clean)
    assert len(docs) == 2

    for doc in docs:
        assert await insert_mapped_event(doc) == "inserted"
        assert await insert_mapped_event(doc) == "skipped"

    count = await test_db.mapped_events.count_documents({"parent_event_id": clean["event_id"]})
    assert count == 2


@pytest.mark.asyncio
async def test_t4_stream_filter_to_sentiment(test_db, redis_client) -> None:
    """clean_event → NER stream → mapped → sentiment stream → sentiment_events."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    clean = _clean_doc()

    for key in (in_stream("ner"), in_stream("sentiment"), in_stream("influence")):
        await redis_client.delete(key)

    reset_ner_pipeline()
    reset_sentiment_pipeline()

    await publish_entry(
        redis_client,
        "ner",
        clean,
        session_id=session_id,
        job_id="job-t4",
        trace_id=str(uuid.uuid4()),
        produced_by="stage:filter",
    )

    ner_processed = await process_batch(
        redis_client,
        "ner",
        ner_processor,
        consumer="ner-int-test",
        block_ms=1000,
    )
    assert ner_processed == 1

    mapped_count = await test_db.mapped_events.count_documents({"parent_event_id": clean["event_id"]})
    assert mapped_count == 2

    sent_processed = await process_batch(
        redis_client,
        "sentiment",
        sentiment_processor,
        consumer="sent-int-test",
        block_ms=1000,
    )
    assert sent_processed == 2
    assert await pending_count(redis_client, "sentiment") == 0

    sentiments = await test_db.sentiment_events.find({"parent_event_id": clean["event_id"]}).to_list(10)
    assert len(sentiments) == 2
    coin_ids = {s["coin_id"] for s in sentiments}
    assert coin_ids == {"BTC", "ETH"}
    for doc in sentiments:
        assert doc.get("filter_meta")
        assert doc.get("ner_meta")
        assert doc["sentiment_label"] in ("positive", "neutral", "negative")


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
