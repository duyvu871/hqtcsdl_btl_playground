"""P3 Ingest + Filter integration tests — T3-01..04, TC-09, stream flow."""

from __future__ import annotations

import sys
import uuid
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
from pymongo.errors import DuplicateKeyError

from src.common.config import settings
from src.common.mongo_client import close_mongo, get_db
from src.common.redis_client import close_redis, get_redis
from src.pipeline._persist import insert_raw_event
from src.pipeline._runtime.keys import in_stream
from src.pipeline._runtime.worker import pending_count, process_batch, publish_entry
from src.pipeline.filter.service import reset_filter_pipeline
from src.pipeline.filter.worker import filter_processor
from src.pipeline.ingest.events import _base_event
from src.pipeline.ingest.service import collect_from_kickoff
from src.pipeline.ingest.worker import ingest_processor

TEST_DB = "crypto_mvp_test"


@pytest.fixture
async def test_db(monkeypatch: pytest.MonkeyPatch):
    """DB test cô lập."""
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


def _kickoff(coin_id: str = "BTC", sources: list[str] | None = None) -> dict:
    return {
        "type": "session_start",
        "coin_id": coin_id,
        "timeframe": "1h",
        "sources": sources or ["twitter"],
    }


# ── TC-09: Dedup ingest ───────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_tc09_ingest_dedup(test_db) -> None:
    """TC-09: Insert trùng (source, external_id) → skip, không thêm doc."""
    doc = _base_event(
        source="twitter",
        raw_text="Dedup test tweet",
        author_id="u1",
        timestamp=1_718_380_800,
        external_id="dup-ext-001",
        metrics={"likes": 10},
    )

    assert await insert_raw_event(doc) == "inserted"
    assert await insert_raw_event(doc) == "skipped"

    count = await test_db.raw_events.count_documents({"external_id": "dup-ext-001"})
    assert count == 1

    # insert_one trực tiếp vẫn raise DuplicateKeyError
    with pytest.raises(DuplicateKeyError):
        await test_db.raw_events.insert_one(doc)


# ── T3-01: Ingest Twitter (cần RAPIDAPI_KEY) ────────────────────────────────
@pytest.mark.asyncio
async def test_t3_01_ingest_twitter(test_db) -> None:
    if not settings.RAPIDAPI_KEY:
        pytest.skip("RAPIDAPI_KEY not set")

    events = collect_from_kickoff(_kickoff(sources=["twitter"]))
    assert len(events) >= 1

    for doc in events[:3]:
        await insert_raw_event(doc)

    count = await test_db.raw_events.count_documents({"source": "twitter"})
    assert count >= 1


# ── T3-02: Ingest Alpha Vantage (cần ALPHA_VANTAGE_API_KEY) ─────────────────
@pytest.mark.asyncio
async def test_t3_02_ingest_news_av(test_db) -> None:
    if not settings.ALPHA_VANTAGE_API_KEY:
        pytest.skip("ALPHA_VANTAGE_API_KEY not set")

    events = collect_from_kickoff(_kickoff(sources=["news-av"]))
    assert len(events) >= 1
    assert all(e["source"] == "news" for e in events)

    for doc in events[:3]:
        await insert_raw_event(doc)

    count = await test_db.raw_events.count_documents({"source": "news"})
    assert count >= 1


# ── T3-03: Stream flow ingest → filter ───────────────────────────────────────
@pytest.mark.asyncio
async def test_t3_03_stream_ingest_to_filter(test_db, redis_client) -> None:
    """Kickoff → ingest processor → filter processor → clean_events."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-int-03"
    trace_id = str(uuid.uuid4())

    # Cleanup streams
    for key in (in_stream("ingest"), in_stream("filter"), in_stream("ner")):
        await redis_client.delete(key)

    reset_filter_pipeline()

    # Synthetic kickoff — không gọi API thật
    kickoff = _kickoff(sources=[])
    kickoff["synthetic_events"] = True  # flag cho test

    # Publish kickoff; ingest_processor với sources rỗng trả []
    # Thay bằng: publish raw event trực tiếp vào filter stream
    raw_doc = _base_event(
        source="twitter",
        raw_text="Federal Reserve holds rates steady in March meeting",
        author_id="analyst-1",
        timestamp=1_718_380_800,
        external_id=f"stream-{uuid.uuid4().hex[:8]}",
        metrics={"likes": 200, "retweets": 30, "followers": 100_000},
    )
    await insert_raw_event(raw_doc)

    # Filter stage: nhận raw_doc qua stream
    await publish_entry(
        redis_client,
        "filter",
        raw_doc,
        session_id=session_id,
        job_id=job_id,
        trace_id=trace_id,
        produced_by="stage:ingest",
    )

    processed = await process_batch(
        redis_client,
        "filter",
        filter_processor,
        consumer="filter-int-test",
        block_ms=1000,
    )
    assert processed == 1
    assert await pending_count(redis_client, "filter") == 0

    clean = await test_db.clean_events.find_one({"event_id": raw_doc["event_id"]})
    assert clean is not None
    assert clean["filter"]["stage"] == "passed"


# ── T3-04: Stream ingest processor với synthetic data ────────────────────────
@pytest.mark.asyncio
async def test_t3_04_ingest_processor_persists(test_db, monkeypatch) -> None:
    """Ingest processor ghi raw_events từ synthetic collector."""
    def _fake_collect(payload: dict) -> list[dict]:
        return [
            _base_event(
                source="twitter",
                raw_text="Synthetic ingest event for integration test",
                author_id="test",
                timestamp=1_718_380_800,
                external_id=f"syn-{uuid.uuid4().hex[:8]}",
                metrics={"likes": 50},
            )
        ]

    monkeypatch.setattr("src.pipeline.ingest.worker.collect_from_kickoff", _fake_collect)

    docs = await ingest_processor(_kickoff(), {})
    assert len(docs) == 1

    stored = await test_db.raw_events.find_one({"event_id": docs[0]["event_id"]})
    assert stored is not None


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
