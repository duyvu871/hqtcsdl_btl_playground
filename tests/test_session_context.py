"""Session context helpers — filter pipeline theo coin/timeframe user chọn."""

from __future__ import annotations

from src.pipeline._runtime.session_context import coin_matches


def test_coin_matches_case_insensitive() -> None:
    assert coin_matches("eth", "ETH")
    assert coin_matches("BTC", "btc")
    assert not coin_matches("BTC", "ETH")
    assert not coin_matches(None, "ETH")


def test_coin_matches_empty() -> None:
    assert not coin_matches("", "BTC")
