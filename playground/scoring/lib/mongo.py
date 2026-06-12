"""Đọc Social Data và lưu tín hiệu (Signals) vào MongoDB."""

from __future__ import annotations
from typing import Any
from pymongo import MongoClient
from lib.config import mongodb_uri, mongodb_db, mapped_collection, signals_collection

def get_db():
    client = MongoClient(mongodb_uri())
    return client[mongodb_db()]

def fetch_social_metrics_realtime(coin_id: str, hours_lookback: int = 24) -> list[dict]:
    """
    (Mẫu) Truy vấn MongoDB aggregate để đếm lượng volume bài viết
    và tính trung bình Sentiment (sau khi bạn làm Bước 4/5).
    """
    # Hiện tại trả về rỗng để làm template cấu trúc
    # Khi ráp DB thật, bạn sẽ dùng lệnh db.mapped_events.aggregate(...) ở đây
    return []

def save_signal(signal_doc: dict[str, Any]) -> None:
    """Ghi kết quả của Bước 6 vào collection signals."""
    col = get_db()[signals_collection()]
    col.insert_one(signal_doc)