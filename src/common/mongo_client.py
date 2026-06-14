"""Async MongoDB client singleton (motor)."""

from __future__ import annotations

from typing import Any

import motor.motor_asyncio
from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase

from src.common.config import settings

_client: AsyncIOMotorClient | None = None


async def get_db() -> AsyncIOMotorDatabase:
    """Return shared AsyncIOMotorDatabase (lazy init)."""
    global _client
    if _client is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(
            settings.MONGODB_URI,
            serverSelectionTimeoutMS=3_000,
        )
    return _client[settings.MONGODB_DB]


async def close_mongo() -> None:
    """Close MongoDB client (for tests / shutdown)."""
    global _client
    if _client is not None:
        _client.close()
        _client = None


async def mongo_ping() -> dict[str, Any]:
    """Health check helper."""
    db = await get_db()
    return await db.command("ping")


async def upsert_stage(
    collection_name: str,
    doc: dict[str, Any],
    unique_keys: list[str],
) -> None:
    """Idempotent upsert by unique key fields (shared by all pipeline stages)."""
    missing = [k for k in unique_keys if k not in doc]
    if missing:
        raise ValueError(f"Document missing unique keys: {missing}")

    db = await get_db()
    filter_ = {k: doc[k] for k in unique_keys}
    await db[collection_name].update_one(filter_, {"$set": doc}, upsert=True)
