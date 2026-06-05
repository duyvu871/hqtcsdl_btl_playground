"""Kết nối MongoDB Atlas và ghi raw events."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from pymongo import ASCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError, OperationFailure

from lib.config import mongodb_collection, mongodb_db, mongodb_uri

if TYPE_CHECKING:
    from lib.progress import Progress

_DEDUP_INDEX = "source_external_id_unique"


def get_collection() -> Collection:
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()][mongodb_collection()]


def ensure_indexes(collection: Collection) -> None:
    collection.create_index([("timestamp", ASCENDING)])
    collection.create_index([("source", ASCENDING)])

    existing = collection.index_information()
    for legacy in ("source_1_external_id_1", _DEDUP_INDEX):
        if legacy in existing:
            collection.drop_index(legacy)

    try:
        collection.create_index(
            [("source", ASCENDING), ("external_id", ASCENDING)],
            unique=True,
            name=_DEDUP_INDEX,
            partialFilterExpression={
                "external_id": {"$exists": True, "$type": "string", "$gt": ""}
            },
        )
    except OperationFailure:
        pass

    if "tweet_id_1" not in collection.index_information():
        collection.create_index("tweet_id", unique=True, sparse=True)


def _normalize_doc(doc: dict[str, Any]) -> dict[str, Any]:
    """Đảm bảo external_id có giá trị khi có thể dedup."""
    out = dict(doc)
    ext = out.get("external_id")
    if not ext and out.get("tweet_id"):
        out["external_id"] = str(out["tweet_id"])
    return out


def insert_events(
    collection: Collection,
    events: list[dict[str, Any]],
    *,
    progress: Progress | None = None,
) -> tuple[int, int]:
    """
    Ghi danh sách events. Bỏ qua bản ghi trùng (source, external_id) hoặc tweet_id.
    Trả về (inserted, skipped_duplicate).
    """
    if not events:
        return 0, 0

    total = len(events)
    inserted = 0
    skipped = 0
    if progress:
        progress.log(f"Ghi MongoDB: 0/{total}...")

    for i, doc in enumerate(events, start=1):
        try:
            collection.insert_one(_normalize_doc(doc))
            inserted += 1
        except DuplicateKeyError:
            skipped += 1
        if progress:
            progress.bar(i, total, prefix="Ghi MongoDB: ")

    return inserted, skipped
