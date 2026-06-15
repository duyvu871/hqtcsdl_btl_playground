#!/usr/bin/env python3
"""CLI: bootstrap MongoDB collections, validators, and indexes."""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
# Cho phép chạy trực tiếp: python scripts/bootstrap_db.py (không qua pytest)
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.common.mongo_client import close_mongo, get_db
from src.common.schema import bootstrap_indexes


async def main() -> int:
    # Dùng MONGODB_URI + MONGODB_DB từ .env (mặc định crypto_mvp)
    db = await get_db()
    count = await bootstrap_indexes(db)
    print(f"Bootstrap complete — {count} indexes ensured")
    await close_mongo()
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
