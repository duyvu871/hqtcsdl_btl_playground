"""Stage 6 — Galaxy dual-score + trading signals."""

from src.pipeline.scoring.documents import build_scoring_signal
from src.pipeline.scoring.market import coin_to_symbol, fetch_market_ohlcv, get_market_ohlcv
from src.pipeline.scoring.mock_data import get_mock_scenario
from src.pipeline.scoring.rules import calc_fractal_swings, calc_kl_divergence, decide_action
from src.pipeline.scoring.score import calculate_dual_scores
from src.pipeline.scoring.service import (
    InsufficientCandlesError,
    ScoringPipeline,
    get_scoring_pipeline,
    reset_scoring_pipeline,
)
from src.pipeline.scoring.transformer import calc_log_return, calc_rolling_zscore
from src.pipeline.scoring.worker import scoring_processor

__all__ = [
    "InsufficientCandlesError",
    "ScoringPipeline",
    "build_scoring_signal",
    "calc_fractal_swings",
    "calc_kl_divergence",
    "calc_log_return",
    "calc_rolling_zscore",
    "calculate_dual_scores",
    "coin_to_symbol",
    "decide_action",
    "fetch_market_ohlcv",
    "get_market_ohlcv",
    "get_mock_scenario",
    "get_scoring_pipeline",
    "reset_scoring_pipeline",
    "scoring_processor",
]
