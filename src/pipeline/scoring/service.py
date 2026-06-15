"""Stage 6 business logic — Galaxy dual-score + signal emission."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import polars as pl

from src.common.config import settings
from src.pipeline.scoring.documents import build_scoring_signal
from src.pipeline.scoring.market import get_market_ohlcv
from src.pipeline.scoring.mock_data import get_mock_scenario
from src.pipeline.scoring.ortho import orthogonalize_momentum
from src.pipeline.scoring.rules import (
    calc_fractal_swings,
    calc_kl_divergence,
    decide_action,
    fractal_confirmed,
    pick_signal_row,
)
from src.pipeline.scoring.score import calculate_dual_scores
from src.pipeline.scoring.transformer import (
    calc_cara_penalty,
    calc_log_return,
    calc_rolling_ols_slope,
    calc_rolling_zscore,
)

logger = logging.getLogger(__name__)


class InsufficientCandlesError(Exception):
    """BUG-03: fail-fast khi không đủ nến join."""


def _normalize_row_ts(value: Any) -> float:
    if isinstance(value, datetime):
        return float(int(value.timestamp()))
    if value is None:
        return 0.0
    return float(value)


def _normalize_social_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for row in rows:
        normalized.append({
            **row,
            "timestamp": _normalize_row_ts(row.get("timestamp")),
        })
    return normalized


@dataclass
class ScoringPipeline:
    """Join social + OHLCV → Galaxy dual-score → BUY/HOLD/SELL."""

    window: int = settings.SCORING_WINDOW
    min_candles: int = settings.SCORING_MIN_CANDLES
    cara_lambda: float = settings.SCORING_CARA_LAMBDA

    def _run_matrix(self, df: pl.DataFrame) -> pl.DataFrame:
        w = self.window
        df = calc_log_return(df, "close")
        df = calc_rolling_zscore(df, "close_log_return", w)
        df = calc_rolling_ols_slope(df, "close", w)
        df = calc_rolling_zscore(df, "close_ols_slope", w)

        df = df.with_columns(pl.col("close_log_return").rolling_std(w).alias("volatility"))
        df = calc_rolling_zscore(df, "volatility", w)
        df = calc_cara_penalty(df, "volatility_zscore", self.cara_lambda)

        df = calc_rolling_zscore(df, "sentiment_score", w)
        df = df.with_columns(pl.col("social_volume").diff().alias("velocity_social"))
        df = df.with_columns((pl.col("social_volume") * pl.col("velocity_social")).alias("impact_raw"))
        df = calc_rolling_zscore(df, "impact_raw", w).rename({"impact_raw_zscore": "Z_impact"})

        df = orthogonalize_momentum(df, ["close_log_return_zscore", "close_ols_slope_zscore"])
        df = calculate_dual_scores(df)
        df = calc_fractal_swings(df, "close", 3)
        return df

    def score_dataframe(self, df: pl.DataFrame) -> dict[str, Any]:
        if df.height < self.min_candles:
            raise InsufficientCandlesError(
                f"Không đủ nến join: {df.height} < {self.min_candles} (BUG-03)"
            )

        scored = self._run_matrix(df)
        recent_p = scored["close"].tail(self.window).to_numpy()
        recent_s = scored["sentiment_score"].tail(self.window).to_numpy()
        kl_div = calc_kl_divergence(recent_p, recent_s)

        latest_rows = scored.filter(
            pl.col("galaxy_alpha_score").is_finite()
            & pl.col("galaxy_safety_score").is_finite()
            & pl.col("close").is_finite()
        )
        if latest_rows.height == 0:
            raise InsufficientCandlesError("Ma trận trống sau rolling window")

        rows = latest_rows.to_dicts()
        latest = pick_signal_row(rows)
        alpha = float(latest["galaxy_alpha_score"])
        safety = float(latest["galaxy_safety_score"])
        action = decide_action(alpha, safety, kl_div, fractal_ok=fractal_confirmed(latest))

        return {
            "action": action,
            "metrics": {
                "galaxy_alpha_score": round(alpha, 2),
                "galaxy_safety_score": round(safety, 2),
                "kl_divergence": round(kl_div, 4),
                "confidence": round(max(0.0, 100 - (kl_div * 10)), 2),
            },
            "execution": {
                "target_price": round(float(latest["close"]) * 1.05, 2),
                "stop_loss": round(float(latest["close"]) * 0.98, 2),
            },
            "timestamp": int(latest["timestamp"]),
            "coin_id": latest.get("coin_id", "BTC"),
        }

    def score_mock(self, scenario_id: str, rows: int = 48) -> dict[str, Any]:
        raw = get_mock_scenario(scenario_id, rows=rows)
        return self.score_dataframe(pl.DataFrame(raw))

    async def score_trigger(self, trigger: dict[str, Any]) -> dict[str, Any]:
        """Score từ batch-trigger transport (social_history + OHLCV)."""
        coin_id = str(trigger.get("coin_id") or "BTC")
        timeframe = str(trigger.get("timeframe") or settings.INFLUENCE_TIMEFRAME)
        social_history = _normalize_social_rows(trigger.get("social_history") or [])

        if not social_history:
            agg = trigger.get("aggregate") or {}
            ws = agg.get("window_start") or agg.get("timestamp")
            social_history = [{
                "timestamp": _normalize_row_ts(ws),
                "coin_id": coin_id,
                "sentiment_score": agg.get("sentiment_score", 0.0),
                "social_volume": agg.get("social_volume", 0),
            }]

        market_list = await get_market_ohlcv(coin_id, timeframe)
        if not market_list:
            raise InsufficientCandlesError(f"Không có OHLCV cho {coin_id}")

        market_df = pl.DataFrame(market_list).sort("timestamp")
        social_df = (
            pl.DataFrame(social_history)
            .sort("timestamp")
            .select(["timestamp", "sentiment_score", "social_volume"])
        )

        # asof join: mỗi nến OHLCV lấy social data gần nhất (backward)
        df = market_df.join_asof(
            social_df,
            on="timestamp",
            strategy="backward",
        ).with_columns([
            pl.col("sentiment_score").fill_null(0.0),
            pl.col("social_volume").fill_null(0),
        ])

        if "coin_id" not in df.columns:
            df = df.with_columns(pl.lit(coin_id).alias("coin_id"))

        result = self.score_dataframe(df)
        return build_scoring_signal(
            coin_id=coin_id,
            timeframe=timeframe,
            action=result["action"],
            metrics=result["metrics"],
            execution=result["execution"],
            timestamp=result["timestamp"],
        )


_pipeline: ScoringPipeline | None = None


def get_scoring_pipeline() -> ScoringPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = ScoringPipeline()
    return _pipeline


def reset_scoring_pipeline() -> None:
    global _pipeline
    _pipeline = None
