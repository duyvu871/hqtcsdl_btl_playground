"""OHLCV adapter — CCXT Binance + Mongo cache (L-02)."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

import ccxt

from src.common.config import settings
from src.common.mongo_client import get_db

logger = logging.getLogger(__name__)


def coin_to_symbol(coin_id: str) -> str:
    return f"{coin_id.upper()}/USDT"


def fetch_market_ohlcv(
    symbol: str = "BTC/USDT",
    timeframe: str = "1h",
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Lấy nến lịch sử từ Binance — trả list {timestamp, close, volume}."""
    lim = limit or settings.SCORING_OHLCV_LIMIT
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=lim)

        market_data: list[dict[str, Any]] = []
        for candle in ohlcv:
            if len(candle) >= 6 and candle[4] is not None and candle[5] is not None:
                market_data.append({
                    "timestamp": candle[0] / 1000.0,
                    "close": float(candle[4]),
                    "volume": float(candle[5]),
                })
        return market_data
    except ccxt.NetworkError:
        logger.warning("CCXT network error fetching %s", symbol)
        return []
    except ccxt.ExchangeError as exc:
        logger.warning("CCXT exchange error %s: %s", symbol, exc)
        return []
    except Exception as exc:
        logger.warning("Market fetch failed %s: %s", symbol, exc)
        return []


async def load_cached_ohlcv(
    coin_id: str,
    timeframe: str,
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Đọc cache market_ohlcv — trả [] nếu miss."""
    lim = limit or settings.SCORING_OHLCV_LIMIT
    db = await get_db()
    cursor = (
        db.market_ohlcv.find({"coin_id": coin_id.upper(), "timeframe": timeframe})
        .sort("timestamp", -1)
        .limit(lim)
    )
    rows = await cursor.to_list(length=lim)
    if not rows:
        return []
    rows.reverse()
    return [
        {
            "timestamp": float(r.get("timestamp", 0)),
            "close": float(r.get("close", 0)),
            "volume": float(r.get("volume", 0)),
        }
        for r in rows
    ]


async def get_market_ohlcv(
    coin_id: str,
    timeframe: str = "1h",
    *,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    """Cache hit → dùng cache; miss → CCXT + persist."""
    lim = limit or settings.SCORING_OHLCV_LIMIT
    cached = await load_cached_ohlcv(coin_id, timeframe, limit=lim)
    if len(cached) >= lim // 2:
        return cached

    symbol = coin_to_symbol(coin_id)
    fresh = fetch_market_ohlcv(symbol, timeframe, limit=lim)
    if fresh:
        from src.pipeline._persist import upsert_market_ohlcv

        await upsert_market_ohlcv(coin_id, timeframe, fresh)
    return fresh
