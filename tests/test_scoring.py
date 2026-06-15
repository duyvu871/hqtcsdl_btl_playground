"""Kiểm tra Scoring stage (Phase 5) — unit test mock scenarios, không cần services.

Chạy: uv run pytest tests/test_scoring.py -v

Danh sách test:
  test_tc07_bullish_divergence_buy    — TC-07 Alpha>60 Safety>40 → BUY
  test_tc08_high_volatility_hold      — TC-08 panic → HOLD
  test_mock_bearish_divergence_sell   — bearish → SELL
  test_t5_02_insufficient_candles     — BUG-03 fail-fast < 15 nến
  test_decide_action_kl_hold          — L-03 KL divergence → HOLD
"""

from __future__ import annotations

import sys
from pathlib import Path

import polars as pl
import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.pipeline.scoring.mock_data import get_mock_scenario
from src.pipeline.scoring.rules import decide_action
from src.pipeline.scoring.service import InsufficientCandlesError, ScoringPipeline


@pytest.fixture
def pipeline() -> ScoringPipeline:
    return ScoringPipeline()


def test_tc07_bullish_divergence_buy(pipeline: ScoringPipeline) -> None:
    """TC-07: bullish divergence → Alpha > 60, Safety > 40 → BUY."""
    result = pipeline.score_mock("bullish_divergence")
    assert result["metrics"]["galaxy_alpha_score"] > 60
    assert result["metrics"]["galaxy_safety_score"] > 40
    assert result["action"] == "BUY"


def test_tc08_high_volatility_hold(pipeline: ScoringPipeline) -> None:
    """TC-08: high volatility panic → Safety thấp, không phát BUY."""
    result = pipeline.score_mock("high_volatility_panic")
    assert result["metrics"]["galaxy_safety_score"] < 40
    assert result["action"] != "BUY"


def test_mock_bearish_divergence_sell(pipeline: ScoringPipeline) -> None:
    """Bearish divergence → Alpha < 40 → SELL."""
    result = pipeline.score_mock("bearish_divergence")
    assert result["metrics"]["galaxy_alpha_score"] < 40
    assert result["action"] == "SELL"


def test_t5_02_insufficient_candles(pipeline: ScoringPipeline) -> None:
    """BUG-03: < 15 nến join → InsufficientCandlesError."""
    raw = get_mock_scenario("bullish_divergence", rows=10)
    df = pl.DataFrame(raw)
    with pytest.raises(InsufficientCandlesError, match="BUG-03"):
        pipeline.score_dataframe(df)


def test_decide_action_kl_hold() -> None:
    """L-03: KL cao + không fractal → HOLD dù alpha/safety đủ BUY."""
    assert decide_action(70, 50, kl_div=0.8, fractal_ok=False) == "HOLD"
    assert decide_action(70, 50, kl_div=0.8, fractal_ok=True) == "BUY"
    assert decide_action(70, 50, kl_div=0.3, fractal_ok=False) == "BUY"
