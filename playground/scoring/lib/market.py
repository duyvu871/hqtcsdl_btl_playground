"""Lấy dữ liệu thị trường (OHLCV) từ sàn giao dịch bằng CCXT."""

from __future__ import annotations
import ccxt
from datetime import datetime, timezone

def fetch_binance_ohlcv(symbol: str = 'BTC/USDT', timeframe: str = '1h', limit: int = 10) -> list[dict]:
    """
    Kéo dữ liệu nến từ Binance. 
    Trả về list dict tương thích với Polars Data Prep.
    """
    exchange = ccxt.binance({
        'enableRateLimit': True,
    })
    
    # Kéo nến
    ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
    
    records = []
    for candle in ohlcv:
        # candle format: [timestamp, open, high, low, close, volume]
        dt = datetime.fromtimestamp(candle[0] / 1000.0, tz=timezone.utc)
        records.append({
            "timestamp": dt.isoformat(),
            "coin_id": symbol.split('/')[0],
            "close": float(candle[4]),
            "volume": float(candle[5])
        })
        
    return records