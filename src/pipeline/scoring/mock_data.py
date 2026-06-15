"""Mock data cho scoring unit tests — port từ playground/scoring/lib/mock_data_v2.py."""

from __future__ import annotations

from datetime import datetime

import numpy as np


def get_mock_scenario(scenario_id: str = "bullish_divergence", rows: int = 48) -> dict[str, list]:
    base_ts = datetime(2026, 6, 14, 0, 0).timestamp()
    rng = np.random.default_rng(42)

    timestamps = [base_ts + i * 3600 for i in range(rows)]
    coin_ids = ["BTC"] * rows

    if scenario_id == "bullish_divergence":
        prices = np.linspace(69500, 67000, rows) + np.sin(np.arange(rows)) * 80
        sentiment = np.linspace(-0.3, 0.75, rows) + rng.normal(0, 0.04, rows)
        social_volume = np.linspace(2000, 8500, rows) + np.sin(np.arange(rows) * 0.8) * 350 + rng.normal(0, 50, rows)
        market_volume = np.linspace(1500, 3500, rows)

    elif scenario_id == "bearish_divergence":
        prices = np.linspace(65000, 72000, rows) + np.cos(np.arange(rows)) * 100
        sentiment = np.linspace(0.6, -0.4, rows) + rng.normal(0, 0.04, rows)
        social_volume = np.linspace(6000, 1800, rows) + np.sin(np.arange(rows) * 0.5) * 200
        market_volume = np.linspace(4000, 1500, rows)

    elif scenario_id == "high_volatility_panic":
        prices = 68000 - (np.arange(rows) ** 1.8) * 4.5
        sentiment = np.linspace(0.1, -0.85, rows) + rng.normal(0, 0.08, rows)
        social_volume = np.linspace(2000, 15000, rows) + rng.normal(0, 500, rows)
        market_volume = np.linspace(1000, 9000, rows)

    else:
        raise ValueError(f"Không tồn tại kịch bản test case: {scenario_id}")

    return {
        "timestamp": timestamps,
        "coin_id": coin_ids,
        "close": prices.tolist(),
        "volume": [float(v) for v in market_volume],
        "social_volume": np.maximum(10, social_volume).tolist(),
        "sentiment_score": sentiment.tolist(),
    }
