"""REST routes — market data."""

from __future__ import annotations

from fastapi import APIRouter, Query

from src.api.services.market_service import get_ohlcv, get_ticker

router = APIRouter(prefix="/market", tags=["market"])


@router.get("/ohlcv")
async def market_ohlcv(
    coin: str = Query("BTC"),
    interval: str = Query("1h"),
    limit: int = Query(48, ge=1, le=500),
) -> dict:
    return await get_ohlcv(coin, interval, limit=limit)


@router.get("/ticker")
async def market_ticker(coin: str = Query("BTC")) -> dict:
    return await get_ticker(coin)
