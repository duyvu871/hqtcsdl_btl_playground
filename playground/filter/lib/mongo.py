"""Đọc raw events và ghi clean/dropped events vào MongoDB."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import (
    clean_collection,
    dropped_collection,
    mongodb_db,
    mongodb_uri,
    raw_collection,
)

if TYPE_CHECKING:
    from lib.progress import Progress


def get_db():
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()]


def get_raw_collection() -> Collection:
    return get_db()[raw_collection()]


def get_clean_collection() -> Collection:
    return get_db()[clean_collection()]


def get_dropped_collection() -> Collection:
    return get_db()[dropped_collection()]


def ensure_indexes(
    clean: Collection,
    dropped: Collection | None = None,
) -> None:
    clean.create_index([("timestamp", ASCENDING)])
    clean.create_index([("source", ASCENDING)])
    clean.create_index("event_id", unique=True)

    if dropped is not None:
        dropped.create_index([("timestamp", ASCENDING)])
        dropped.create_index("event_id", unique=True, sparse=True)


def fetch_unprocessed_raw(
    raw: Collection,
    clean: Collection,
    *,
    limit: int | None = None,
    source: str | None = None,
    since_ts: int | None = None,
) -> list[dict[str, Any]]:
    """Lấy raw events chưa có bản ghi tương ứng trong clean_events."""
    processed_ids = clean.distinct("event_id")
    query: dict[str, Any] = {"event_id": {"$nin": processed_ids}}
    if source:
        query["source"] = source
    if since_ts is not None:
        query["timestamp"] = {"$gte": since_ts}

    cursor = raw.find(query).sort("timestamp", ASCENDING)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def build_clean_doc(raw: dict[str, Any], *, filter_meta: dict[str, Any]) -> dict[str, Any]:
    """Map raw event → clean event contract (Stage 2 output, trước NER)."""
    doc: dict[str, Any] = {
        "event_id": raw["event_id"],
        "source": raw.get("source"),
        "raw_text": raw.get("raw_text", ""),
        "clean_text": filter_meta.get("clean_text") or raw.get("raw_text", ""),
        "author_id": raw.get("author_id", "unknown"),
        "metrics": raw.get("metrics") or {},
        "timestamp": raw.get("timestamp"),
        "is_spam": False,
        "filter": filter_meta,
        "filtered_at": _now_ts(),
    }
    for key in (
        "external_id",
        "tweet_id",
        "link_meta",
        "language",
        "ingested_at",
        "news_provider",
        "subreddit",
        "reddit_fetch_mode",
        "related_tickers",
    ):
        if key in raw:
            doc[key] = raw[key]
    return doc


def build_dropped_doc(
    raw: dict[str, Any],
    *,
    reason: str,
    stage: str,
    filter_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "event_id": raw.get("event_id"),
        "source": raw.get("source"),
        "raw_text": raw.get("raw_text", ""),
        "author_id": raw.get("author_id"),
        "timestamp": raw.get("timestamp"),
        "drop_reason": reason,
        "drop_stage": stage,
        "filter": filter_meta or {},
        "dropped_at": _now_ts(),
    }


def insert_clean(
    collection: Collection,
    docs: list[dict[str, Any]],
    *,
    progress: Progress | None = None,
) -> tuple[int, int]:
    if not docs:
        return 0, 0

    total = len(docs)
    inserted = 0
    skipped = 0
    if progress:
        progress.log(f"Ghi clean_events: 0/{total}...")

    for i, doc in enumerate(docs, start=1):
        try:
            collection.insert_one(doc)
            inserted += 1
        except DuplicateKeyError:
            skipped += 1
        if progress:
            progress.bar(i, total, prefix="Ghi clean: ")

    return inserted, skipped


def insert_dropped(
    collection: Collection,
    docs: list[dict[str, Any]],
    *,
    progress: Progress | None = None,
) -> tuple[int, int]:
    if not docs:
        return 0, 0

    total = len(docs)
    inserted = 0
    skipped = 0
    if progress:
        progress.log(f"Ghi dropped_events: 0/{total}...")

    for i, doc in enumerate(docs, start=1):
        try:
            collection.insert_one(doc)
            inserted += 1
        except DuplicateKeyError:
            skipped += 1
        if progress:
            progress.bar(i, total, prefix="Ghi dropped: ")

    return inserted, skipped
