"""MongoDB I/O — đọc mapped/clean events, ghi sentiment_events."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import (
    aggregate_collection,
    clean_collection,
    mapped_collection,
    mongodb_db,
    mongodb_uri,
    sentiment_collection,
)


def get_db():
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()]


def get_mapped_collection() -> Collection:
    return get_db()[mapped_collection()]


def get_clean_collection() -> Collection:
    return get_db()[clean_collection()]


def get_sentiment_collection() -> Collection:
    return get_db()[sentiment_collection()]


def get_aggregate_collection() -> Collection:
    return get_db()[aggregate_collection()]


def ensure_indexes(db) -> None:
    """Tạo index cho sentiment_events và sentiment_aggregates."""
    sent_col = db[sentiment_collection()]
    agg_col = db[aggregate_collection()]

    # Chống duplicate: mapped_id + coin_id
    sent_col.create_index(
        [("mapped_id", ASCENDING), ("coin_id", ASCENDING)],
        unique=True,
        sparse=True,
        name="uq_mapped_coin",
    )
    # Chống duplicate: event_id + coin_id
    sent_col.create_index(
        [("event_id", ASCENDING), ("coin_id", ASCENDING)],
        unique=True,
        sparse=True,
        name="uq_event_coin",
    )
    # Query theo coin + thời gian
    sent_col.create_index(
        [("coin_id", ASCENDING), ("timestamp", ASCENDING)],
        name="idx_coin_ts",
    )

    # Aggregate unique index
    agg_col.create_index(
        [("coin_id", ASCENDING), ("timeframe", ASCENDING), ("window_start", ASCENDING)],
        unique=True,
        name="uq_coin_tf_window",
    )


def fetch_input_events(
    db,
    *,
    limit: int | None = None,
    source: str | None = None,
    since_ts: int | None = None,
) -> tuple[Collection, list[dict[str, Any]]]:
    """Đọc mapped_events trước; nếu rỗng thì fallback clean_events.
    
    Chỉ lấy event có coin_id và clean_text.
    Bỏ qua event đã có trong sentiment_events.
    """
    sent_col = db[sentiment_collection()]

    # Thử mapped_events trước
    mapped_col = db[mapped_collection()]
    events = _query_events(mapped_col, sent_col, limit=limit, source=source, since_ts=since_ts)
    if events:
        return mapped_col, events

    # Fallback sang clean_events
    clean_col = db[clean_collection()]
    events = _query_events(clean_col, sent_col, limit=limit, source=source, since_ts=since_ts)
    return clean_col, events


def _query_events(
    input_col: Collection,
    sent_col: Collection,
    *,
    limit: int | None = None,
    source: str | None = None,
    since_ts: int | None = None,
) -> list[dict[str, Any]]:
    """Query input collection, loại bỏ event đã score."""
    query: dict[str, Any] = {
        "coin_id": {"$exists": True, "$ne": None},
        "clean_text": {"$exists": True, "$ne": ""},
    }
    if source:
        query["source"] = source
    if since_ts is not None:
        query["timestamp"] = {"$gte": since_ts}

    cursor = input_col.find(query).sort("timestamp", ASCENDING)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def already_scored(sent_col: Collection, event: dict[str, Any]) -> bool:
    """Kiểm tra event đã được score chưa."""
    coin_id = event.get("coin_id")
    if not coin_id:
        return False

    # Ưu tiên check mapped_id
    mapped_id = event.get("mapped_id")
    if mapped_id:
        return sent_col.find_one(
            {"mapped_id": mapped_id, "coin_id": coin_id}, {"_id": 1}
        ) is not None

    # Fallback check event_id
    event_id = event.get("event_id")
    if event_id:
        return sent_col.find_one(
            {"event_id": event_id, "coin_id": coin_id}, {"_id": 1}
        ) is not None

    return False


def insert_sentiment(
    collection: Collection,
    doc: dict[str, Any],
) -> bool:
    """Insert 1 sentiment_event. Return True nếu thành công."""
    try:
        collection.insert_one(doc)
        return True
    except DuplicateKeyError:
        return False
