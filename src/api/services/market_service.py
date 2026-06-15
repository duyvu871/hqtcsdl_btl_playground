"""Market data cho REST API — OHLCV + ticker."""

from __future__ import annotations

import logging
from typing import Any

from src.common.mongo_client import get_db

logger = logging.getLogger(__name__)


def _coin_symbol(coin_id: str) -> str:
    return f"{coin_id.upper()}/USDT"


def _import_ccxt():
    """Lazy import — ccxt nằm trong extra `api` hoặc `pipeline`."""
    try:
        import ccxt

        return ccxt
    except ImportError:
        logger.debug("ccxt not installed — uv sync --extra api")
        return None


def _candle_from_row(row: dict[str, Any]) -> dict[str, Any]:
    """Chuẩn hóa 1 nến → TradingView format."""
    ts = row.get("timestamp", 0)
    if isinstance(ts, float):
        time_ms = int(ts * 1000) if ts < 1e12 else int(ts)
    else:
        time_ms = int(ts)
        if time_ms < 1e12:
            time_ms *= 1000

    close = float(row.get("close", 0))
    open_ = float(row.get("open", close))
    high = float(row.get("high", max(open_, close)))
    low = float(row.get("low", min(open_, close)))
    volume = float(row.get("volume", 0))

    return {
        "time": time_ms,
        "open": open_,
        "high": high,
        "low": low,
        "close": close,
        "volume": volume,
    }


async def _load_cached_candles(coin_id: str, interval: str, limit: int) -> list[dict[str, Any]]:
    db = await get_db()
    cursor = (
        db.market_ohlcv.find({"coin_id": coin_id.upper(), "timeframe": interval})
        .sort("timestamp", -1)
        .limit(limit)
    )
    rows = await cursor.to_list(length=limit)
    rows.reverse()
    return [_candle_from_row(r) for r in rows]


def _fetch_ccxt_ohlcv(coin_id: str, interval: str, limit: int) -> list[dict[str, Any]]:
    ccxt = _import_ccxt()
    if ccxt is None:
        return []

    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        raw = exchange.fetch_ohlcv(_coin_symbol(coin_id), interval, limit=limit)
        candles: list[dict[str, Any]] = []
        for row in raw:
            if len(row) < 6:
                continue
            candles.append({
                "time": int(row[0]),
                "open": float(row[1]),
                "high": float(row[2]),
                "low": float(row[3]),
                "close": float(row[4]),
                "volume": float(row[5]),
            })
        return candles
    except Exception as exc:
        logger.warning("CCXT OHLCV failed %s: %s", coin_id, exc)
        return []


async def _ticker_from_cache(coin_id: str) -> dict[str, Any] | None:
    candles = await _load_cached_candles(coin_id, "1h", 2)
    if len(candles) < 2:
        return None
    prev, last = candles[-2], candles[-1]
    prev_close = float(prev["close"])
    last_close = float(last["close"])
    change = ((last_close - prev_close) / prev_close * 100) if prev_close else 0.0
    return {
        "coin": coin_id.upper(),
        "last": last_close,
        "change_pct": round(change, 2),
        "volume": float(last.get("volume", 0)),
    }


async def get_ohlcv(coin_id: str, interval: str = "1h", *, limit: int = 48) -> dict[str, Any]:
    """OHLCV cho TradingView datafeed."""
    candles = _fetch_ccxt_ohlcv(coin_id, interval, limit)
    if not candles:
        candles = await _load_cached_candles(coin_id, interval, limit)
    return {"coin": coin_id.upper(), "interval": interval, "candles": candles}


async def get_ticker(coin_id: str) -> dict[str, Any]:
    """Giá realtime — last, change_pct, volume."""
    ccxt = _import_ccxt()
    if ccxt is not None:
        try:
            exchange = ccxt.binance({"enableRateLimit": True})
            ticker = exchange.fetch_ticker(_coin_symbol(coin_id))
            return {
                "coin": coin_id.upper(),
                "last": float(ticker.get("last") or 0),
                "change_pct": float(ticker.get("percentage") or 0),
                "volume": float(ticker.get("quoteVolume") or ticker.get("baseVolume") or 0),
            }
        except Exception as exc:
            logger.warning("CCXT ticker failed %s: %s", coin_id, exc)

    cached = await _ticker_from_cache(coin_id)
    if cached:
        return cached

    return {"coin": coin_id.upper(), "last": 0.0, "change_pct": 0.0, "volume": 0.0}
