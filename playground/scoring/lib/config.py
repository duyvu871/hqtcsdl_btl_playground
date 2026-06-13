"""Quản lý cấu hình và biến môi trường cho Bước 6."""

from __future__ import annotations
import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env từ thư mục scoring
_ENV_FILE = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(_ENV_FILE)

def _require(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"Thiếu {name}. Hãy kiểm tra file .env")
    return value

def mongodb_uri() -> str:
    return _require("MONGODB_URI")

def mongodb_db() -> str:
    return os.getenv("MONGODB_DB", "crypto_mvp").strip()

def mapped_collection() -> str:
    return os.getenv("MONGODB_MAPPED_COLLECTION", "mapped_events").strip()

def signals_collection() -> str:
    return os.getenv("MONGODB_SIGNALS_COLLECTION", "signals").strip()