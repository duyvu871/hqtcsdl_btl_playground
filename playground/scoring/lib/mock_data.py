"""Dữ liệu giả lập (Mock Data) cho Bước 6."""

from __future__ import annotations

# 1. DỮ LIỆU THỊ TRƯỜNG (MARKET DATA - OHLCV)
# Giả lập nến 1h từ sàn giao dịch (Binance)
MOCK_MARKET_DATA = [
    {"timestamp": "2026-06-12T09:00:00", "coin_id": "BTC", "close": 70000.0, "volume": 1000},
    {"timestamp": "2026-06-12T10:00:00", "coin_id": "BTC", "close": 69500.0, "volume": 1200}, # Bắt đầu giảm
    {"timestamp": "2026-06-12T11:00:00", "coin_id": "BTC", "close": 68000.0, "volume": 2500}, # Giá giảm sâu
    {"timestamp": "2026-06-12T12:00:00", "coin_id": "BTC", "close": 67500.0, "volume": 3000}, # Giá vẫn giảm
    {"timestamp": "2026-06-12T13:00:00", "coin_id": "BTC", "close": 69000.0, "volume": 4000}, # Pump mạnh
]

# 2. DỮ LIỆU MẠNG XÃ HỘI (SOCIAL DATA)
# Giả lập dữ liệu đã qua Bước 4 (Sentiment) và Bước 5 (Influence)
# sentiment_score: -1.0 (Cực đoan tiêu cực/FUD) đến 1.0 (Cực đoan tích cực/FOMO)
MOCK_SOCIAL_DATA = [
    {"timestamp": "2026-06-12T09:00:00", "coin_id": "BTC", "social_volume": 1000, "sentiment_score": 0.0},
    {"timestamp": "2026-06-12T10:00:00", "coin_id": "BTC", "social_volume": 1200, "sentiment_score": -0.2}, 
    {"timestamp": "2026-06-12T11:00:00", "coin_id": "BTC", "social_volume": 5000, "sentiment_score": 0.5}, # Dấu hiệu Divergence: Giá giảm, nhưng người ta nói về BTC cực nhiều & tích cực
    {"timestamp": "2026-06-12T12:00:00", "coin_id": "BTC", "social_volume": 8000, "sentiment_score": 0.8}, # Bullish Divergence mạnh nhất
    {"timestamp": "2026-06-12T13:00:00", "coin_id": "BTC", "social_volume": 4000, "sentiment_score": 0.1}, # Sentiment quay đầu giảm
]