"""MongoDB I/O — đọc clean/raw events, ghi mapped_events (fan-out)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import (
    clean_collection,
    mapped_collection,
    mongodb_db,
    mongodb_uri,
    raw_collection,
)
from lib.pipeline import NerOutcome
from lib.rules import Mention

if TYPE_CHECKING:
    from lib.progress import Progress


def get_db():
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()]


def get_raw_collection() -> Collection:
    return get_db()[raw_collection()]


def get_clean_collection() -> Collection:
    return get_db()[clean_collection()]


def get_mapped_collection() -> Collection:
    return get_db()[mapped_collection()]


def ensure_indexes(mapped: Collection) -> None:
    mapped.create_index([("timestamp", ASCENDING)])
    mapped.create_index([("coin_id", ASCENDING)])
    mapped.create_index([("parent_event_id", ASCENDING)])
    mapped.create_index([("parent_event_id", ASCENDING), ("coin_id", ASCENDING)], unique=True)


def fetch_input_events(
    source_col: Collection,
    mapped: Collection,
    *,
    limit: int | None = None,
    source: str | None = None,
    since_ts: int | None = None,
    reprocess: bool = False,
) -> list[dict[str, Any]]:
    """Events từ source; mặc định bỏ qua parent_event_id đã có trong mapped_events."""
    query: dict[str, Any] = {}
    if not reprocess:
        processed_ids = mapped.distinct("parent_event_id")
        query["event_id"] = {"$nin": processed_ids}
    if source:
        query["source"] = source
    if since_ts is not None:
        query["timestamp"] = {"$gte": since_ts}

    cursor = source_col.find(query).sort("timestamp", ASCENDING)
    if limit:
        cursor = cursor.limit(limit)
    return list(cursor)


def fetch_unprocessed_input(
    source_col: Collection,
    mapped: Collection,
    *,
    limit: int | None = None,
    source: str | None = None,
    since_ts: int | None = None,
) -> list[dict[str, Any]]:
    return fetch_input_events(
        source_col,
        mapped,
        limit=limit,
        source=source,
        since_ts=since_ts,
        reprocess=False,
    )


def clear_mapped_for_events(mapped: Collection, event_ids: list[str]) -> int:
    if not event_ids:
        return 0
    result = mapped.delete_many({"parent_event_id": {"$in": event_ids}})
    return int(result.deleted_count)


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def build_mapped_docs(
    event: dict[str, Any],
    mentions: list[Mention],
    outcome: NerOutcome,
) -> list[dict[str, Any]]:
    parent_id = event.get("event_id")
    clean_text = str(event.get("clean_text") or event.get("raw_text") or "")
    docs: list[dict[str, Any]] = []

    for mention in mentions:
        doc: dict[str, Any] = {
            "mapped_id": str(uuid.uuid4()),
            "parent_event_id": parent_id,
            "event_id": parent_id,
            "coin_id": mention.coin_id,
            "source": event.get("source"),
            "clean_text": clean_text,
            "author_id": event.get("author_id", "unknown"),
            "metrics": event.get("metrics") or {},
            "timestamp": event.get("timestamp"),
            "is_spam": event.get("is_spam", False),
            "ner": {
                "mode": outcome.mode,
                "method": mention.method,
                "evidence": mention.evidence,
                "confidence": mention.confidence,
                "used_llm": outcome.used_llm,
                "notes": outcome.notes,
                "llm_error": outcome.llm_error,
            },
            "mapped_at": _now_ts(),
        }
        for key in (
            "external_id",
            "tweet_id",
            "link_meta",
            "language",
            "news_provider",
            "related_tickers",
            "subreddit",
        ):
            if key in event:
                doc[key] = event[key]
        docs.append(doc)

    return docs


def insert_mapped(
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
        progress.log(f"Ghi mapped_events: 0/{total}...")

    for i, doc in enumerate(docs, start=1):
        try:
            collection.insert_one(doc)
            inserted += 1
        except DuplicateKeyError:
            skipped += 1
        if progress:
            progress.bar(i, total, prefix="Ghi mapped: ")

    return inserted, skipped
