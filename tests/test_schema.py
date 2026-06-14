"""Kiểm tra schema MongoDB (Phase 1) — index, unique, validation.

Chạy: uv run pytest tests/test_schema.py -v
Cần: MongoDB (docker compose). Dùng DB riêng crypto_mvp_test, tự xóa sau test.

Danh sách test:
  test_t1_01_bootstrap_idempotent     — chạy bootstrap 2 lần không lỗi
  test_t1_02_raw_events_unique_dedup  — trùng (source, external_id) bị chặn
  test_t1_03_mapped_events_unique     — trùng (parent_event_id, coin_id) bị chặn
  test_t1_04_influence_aggregates     — upsert cùng cửa sổ không tạo doc thừa
  test_t1_05_chat_messages_explain    — query session_id dùng đúng index
  test_t1_06_all_collections_exist    — đủ 14 collection sau bootstrap
  test_t1_07_jsonschema_rejects       — doc thiếu field bắt buộc bị từ chối
"""

from __future__ import annotations

import sys
from pathlib import Path

# Required when running: python tests/test_schema.py (pytest sets pythonpath via pyproject).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from datetime import datetime, timezone
from typing import Any

import pytest
from pymongo.errors import DuplicateKeyError, WriteError

from src.common.mongo_client import close_mongo, get_db, upsert_stage
from src.common.schema import COLLECTIONS, bootstrap_indexes

TEST_DB = "crypto_mvp_test"  # DB riêng, không ảnh hưởng crypto_mvp dev
UTC = timezone.utc


def _plan_uses_index(plan: dict[str, Any], index_name: str) -> bool:
    """Duyệt cây explain plan — MongoDB có thể nest inputStage nhiều tầng."""
    if plan.get("indexName") == index_name:
        return True
    for key in ("inputStage", "inputStages", "shards"):
        child = plan.get(key)
        if isinstance(child, dict) and _plan_uses_index(child, index_name):
            return True
        if isinstance(child, list):
            return any(_plan_uses_index(item, index_name) for item in child)
    return False


@pytest.fixture
async def test_db(monkeypatch: pytest.MonkeyPatch):
    """DB test cô lập: bootstrap trước test, drop database sau test."""
    monkeypatch.setattr("src.common.config.settings.MONGODB_DB", TEST_DB)
    await close_mongo()  # reset singleton để get_db() dùng TEST_DB mới

    try:
        db = await get_db()
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


def _raw_event(event_id: str = "evt-001", external_id: str = "ext-001") -> dict[str, Any]:
    """Document mẫu hợp lệ cho raw_events — dùng chung T1-02."""
    return {
        "event_id": event_id,
        "source": "twitter",
        "external_id": external_id,
        "raw_text": "Bitcoin breaking out",
        "timestamp": 1_718_380_800,
    }


@pytest.mark.asyncio
async def test_t1_01_bootstrap_idempotent(test_db) -> None:
    """Chạy bootstrap_indexes nhiều lần vẫn ổn — không crash, không trùng lỗi."""
    count_first = await bootstrap_indexes(test_db)
    count_second = await bootstrap_indexes(test_db)
    assert count_first > 0
    assert count_second > 0


@pytest.mark.asyncio
async def test_t1_02_raw_events_unique_dedup(test_db) -> None:
    """Hai tweet cùng nguồn + cùng external_id — lần 2 insert bị từ chối."""
    doc = _raw_event()
    await test_db.raw_events.insert_one(doc)
    with pytest.raises(DuplicateKeyError):
        # Cùng (source, external_id) nhưng event_id khác → index uq_source_extid chặn
        await test_db.raw_events.insert_one(_raw_event(event_id="evt-002"))


@pytest.mark.asyncio
async def test_t1_03_mapped_events_unique_fanout(test_db) -> None:
    """Hai mapped event cùng parent + coin — lần 2 insert bị từ chối."""
    doc = {
        "mapped_id": "map-001",
        "parent_event_id": "evt-parent",
        "coin_id": "BTC",
    }
    await test_db.mapped_events.insert_one(doc)
    dup = {**doc, "mapped_id": "map-002"}  # mapped_id khác nhưng (parent, coin) trùng
    with pytest.raises(DuplicateKeyError):
        await test_db.mapped_events.insert_one(dup)


@pytest.mark.asyncio
async def test_t1_04_influence_aggregates_upsert(test_db) -> None:
    """Ghi aggregate cùng coin + timeframe + window 2 lần — chỉ 1 doc, giá trị mới nhất."""
    window_start = datetime(2026, 6, 14, 10, 0, 0, tzinfo=UTC)
    base = {
        "coin_id": "BTC",
        "timeframe": "1h",
        "window_start": window_start,
        "sentiment_score": 0.5,
        "social_volume": 10,
    }
    keys = ["coin_id", "timeframe", "window_start"]  # khớp unique index uq_agg_window

    await upsert_stage("influence_aggregates", {**base, "total_influence": 1.0}, keys)
    await upsert_stage("influence_aggregates", {**base, "total_influence": 2.0}, keys)  # ghi đè

    count = await test_db.influence_aggregates.count_documents(
        {"coin_id": "BTC", "timeframe": "1h", "window_start": window_start}
    )
    assert count == 1
    doc = await test_db.influence_aggregates.find_one(
        {"coin_id": "BTC", "timeframe": "1h", "window_start": window_start}
    )
    assert doc is not None
    assert doc["total_influence"] == 2.0


@pytest.mark.asyncio
async def test_t1_05_chat_messages_explain_uses_index(test_db) -> None:
    """Tìm chat theo session_id — MongoDB dùng index, không quét full collection."""
    now = datetime(2026, 6, 14, 12, 0, 0, tzinfo=UTC)
    await test_db.chat_messages.insert_many(
        [
            {
                "message_id": "msg-001",
                "session_id": "sess-explain",
                "role": "user",
                "type": "text",
                "content": "Analyze BTC",
                "created_at": now,
            },
            {
                "message_id": "msg-002",
                "session_id": "sess-other",
                "role": "user",
                "type": "text",
                "content": "Other session",
                "created_at": now,
            },
        ]
    )

    explain = await test_db.chat_messages.find({"session_id": "sess-explain"}).explain()
    winning = explain.get("queryPlanner", {}).get("winningPlan", {})
    assert _plan_uses_index(winning, "idx_session_created")


@pytest.mark.asyncio
async def test_t1_06_all_collections_exist(test_db) -> None:
    """Sau bootstrap có đủ 14 collection theo thiết kế."""
    names = set(await test_db.list_collection_names())
    for coll in COLLECTIONS:
        assert coll in names, f"Missing collection: {coll}"
    assert len(COLLECTIONS) == 14


@pytest.mark.asyncio
async def test_t1_07_jsonschema_rejects_invalid_doc(test_db) -> None:
    """Ghi doc thiếu event_id — MongoDB $jsonSchema từ chối."""
    invalid = {
        # Thiếu event_id (required) → MongoDB $jsonSchema reject
        "source": "twitter",
        "raw_text": "missing event_id",
        "timestamp": 1_718_380_800,
    }
    with pytest.raises(WriteError) as exc_info:
        await test_db.raw_events.insert_one(invalid)
    assert exc_info.value.code == 121  # DocumentValidationFailure


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
