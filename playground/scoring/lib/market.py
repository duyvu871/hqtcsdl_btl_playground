"""Adapter kéo nến Binance an toàn."""
import ccxt

def fetch_market_ohlcv(symbol: str = "BTC/USDT", timeframe: str = "1h", limit: int = 48) -> list[dict]:
    """Lấy dữ liệu nến đóng cửa lịch sử từ Binance kèm cơ chế chống lỗi dữ liệu rỗng."""
    try:
        exchange = ccxt.binance({"enableRateLimit": True})
        ohlcv = exchange.fetch_ohlcv(symbol, timeframe, limit=limit)
        
        market_data = []
        for candle in ohlcv:
            # Kiểm tra an toàn (Safe Check): Bỏ qua các nến bị lỗi API trả về None
            if len(candle) >= 6 and candle[4] is not None and candle[5] is not None:
                market_data.append({
                    "timestamp": candle[0] / 1000.0, # Convert miliseconds to seconds
                    "close": float(candle[4]),
                    "volume": float(candle[5])
                })
                
        return market_data
        
    except ccxt.NetworkError as e:
        print(f"⚠️ Lỗi mạng khi kết nối Binance API: Lỗi đường truyền hoặc bị chặn IP.")
        return []
    except ccxt.ExchangeError as e:
        print(f"⚠️ Lỗi từ phía sàn Binance (Có thể sai Symbol hoặc tham số): {e}")
        return []
    except Exception as e:
        print(f"⚠️ Lỗi hệ thống không xác định trong market.py: {e}")
        return []