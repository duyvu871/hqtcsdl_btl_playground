"""Đọc sentiment aggregates (Bước 4) và ghi scoring signals (Bước 6) vào MongoDB."""

from __future__ import annotations

from typing import Any

from pymongo import ASCENDING, DESCENDING, MongoClient
from pymongo.collection import Collection
from pymongo.errors import DuplicateKeyError

from lib.config import (
    aggregate_collection,
    mongodb_db,
    mongodb_uri,
    signal_collection,
)

# Khởi tạo client tĩnh trong module để tái sử dụng connection pool
_CLIENT: MongoClient | None = None


def get_db():
    global _CLIENT
    if _CLIENT is None:
        _CLIENT = MongoClient(mongodb_uri())
    return _CLIENT[mongodb_db()]


def get_aggregate_collection() -> Collection:
    return get_db()[aggregate_collection()]


def get_signal_collection() -> Collection:
    return get_db()[signal_collection()]


def ensure_indexes(signal_col: Collection) -> None:
    """Tạo index để truy vấn tín hiệu nhanh và chống lưu trùng payload."""
    signal_col.create_index([("timestamp", DESCENDING)])
    signal_col.create_index([("coin_id", ASCENDING)])
    # Chống duplicate tín hiệu thông qua signal_id (UUID)
    signal_col.create_index("signal_id", unique=True)


def fetch_sentiment_metrics(
    coin_id: str = "BTC",
    timeframe: str = "1h",
    limit: int = 48
) -> list[dict[str, Any]]:
    """Truy vấn dữ liệu tâm lý đã qua xử lý (Output của Bước 4)."""
    col = get_aggregate_collection()
    query = {"coin_id": coin_id, "timeframe": timeframe}

    # Kéo các bản ghi mới nhất
    cursor = col.find(query).sort("window_start", DESCENDING).limit(limit)
    raw_docs = list(cursor)

    if not raw_docs:
        return []

    # Đảo ngược mảng để dữ liệu chảy đúng chiều thời gian từ cũ -> mới (Time-series)
    raw_docs = raw_docs[::-1]

    formatted_metrics = []
    for doc in raw_docs:
        formatted_metrics.append({
            "timestamp": doc["window_start"].timestamp(),
            "coin_id": doc["coin_id"],
            "social_volume": float(doc.get("event_count", 0)),
            "sentiment_score": float(doc.get("weighted_sentiment", 0.0))
        })

    return formatted_metrics


def insert_signals(
    collection: Collection,
    docs: list[dict[str, Any]]
) -> tuple[int, int]:
    """
    Ghi hợp đồng dữ liệu đầu ra (Data Contract) vào MongoDB.
    Returns: Tuple (số bản ghi thành công, số bản ghi bị bỏ qua do trùng lặp).
    """
    if not docs:
        return 0, 0

    inserted = 0
    skipped = 0

    for doc in docs:
        try:
            collection.insert_one(doc)
            inserted += 1
        except DuplicateKeyError:
            skipped += 1

    return inserted, skipped