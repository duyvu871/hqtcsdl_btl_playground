"""MongoDB I/O cho Stage 5.

Chỉ đọc `sentiment_events` và chỉ ghi `weighted_events` / `influence_aggregates`.
Không sửa các collection của Stage 4 hoặc Stage 6.
"""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import (
    influence_agg_collection,
    mongodb_db,
    mongodb_uri,
    sentiment_collection,
    weighted_collection,
)
from lib.schema import build_weighted_event


def get_db():
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()]


def get_sentiment_collection() -> Collection:
    return get_db()[sentiment_collection()]


def get_weighted_collection() -> Collection:
    return get_db()[weighted_collection()]


def get_influence_agg_collection() -> Collection:
    return get_db()[influence_agg_collection()]


def ensure_indexes(db) -> None:
    sent_col = db[sentiment_collection()]
    weighted_col = db[weighted_collection()]
    agg_col = db[influence_agg_collection()]

    sent_col.create_index([("timestamp", ASCENDING)])
    sent_col.create_index([("coin_id", ASCENDING)])
    sent_col.create_index([("source", ASCENDING)])
    sent_col.create_index([("sentiment_id", ASCENDING)])

    weighted_col.create_index([("source_event_key", ASCENDING)], unique=True)
    weighted_col.create_index([("timestamp", ASCENDING)])
    weighted_col.create_index([("coin_id", ASCENDING)])
    weighted_col.create_index([("source", ASCENDING)])
    weighted_col.create_index([("author_id", ASCENDING)])
    weighted_col.create_index([("coin_id", ASCENDING), ("timestamp", ASCENDING)])

    agg_col.create_index(
        [("coin_id", ASCENDING), ("timeframe", ASCENDING), ("window_start", ASCENDING)],
        unique=True,
    )
    agg_col.create_index([("timestamp", DESCENDING)])


def _processed_keys(weighted_col: Collection) -> set[str]:
    return {str(value) for value in weighted_col.distinct("source_event_key") if value}


def _source_event_key_expr(event: dict[str, Any]) -> str:
    for key in ("sentiment_id", "mapped_id"):
        value = event.get(key)
        if value:
            return str(value)
    event_id = event.get("event_id") or event.get("parent_event_id") or "unknown_event"
    coin_id = event.get("coin_id") or "unknown_coin"
    return f"{event_id}:{coin_id}"


def fetch_sentiment_events(
    sent_col: Collection,
    weighted_col: Collection,
    *,
    limit: int | None = None,
    source: str | None = None,
    coin_id: str | None = None,
    since_ts: int | None = None,
    reprocess: bool = False,
) -> list[dict[str, Any]]:
    """Lấy input từ Stage 4 sentiment_events."""
    query: dict[str, Any] = {
        "coin_id": {"$exists": True, "$ne": None},
        "sentiment_score": {"$exists": True, "$ne": None},
    }
    if source:
        query["source"] = source
    if coin_id:
        query["coin_id"] = coin_id.upper()
    if since_ts is not None:
        query["timestamp"] = {"$gte": int(since_ts)}

    cursor = sent_col.find(query).sort("timestamp", ASCENDING)
    if limit:
        cursor = cursor.limit(limit)

    events = list(cursor)
    if reprocess or not events:
        return events

    processed = _processed_keys(weighted_col)
    return [event for event in events if _source_event_key_expr(event) not in processed]


def insert_weighted_events(
    weighted_col: Collection,
    docs: list[dict[str, Any]],
    *,
    replace: bool = False,
) -> tuple[int, int]:
    """Insert/upsert weighted_events.

    Returns:
        (inserted_or_upserted, skipped_duplicate)
    """
    inserted = 0
    skipped = 0

    for doc in docs:
        try:
            if replace:
                weighted_col.update_one(
                    {"source_event_key": doc["source_event_key"]},
                    {"$set": doc},
                    upsert=True,
                )
                inserted += 1
            else:
                weighted_col.insert_one(doc)
                inserted += 1
        except DuplicateKeyError:
            skipped += 1

    return inserted, skipped


def build_weighted_documents(
    events: list[dict[str, Any]],
    *,
    reference_ts: int | None = None,
) -> list[dict[str, Any]]:
    return [build_weighted_event(event, reference_ts=reference_ts) for event in events]


def collection_stats(db) -> dict[str, int]:
    return {
        sentiment_collection(): db[sentiment_collection()].count_documents({}),
        weighted_collection(): db[weighted_collection()].count_documents({}),
        influence_agg_collection(): db[influence_agg_collection()].count_documents({}),
    }
