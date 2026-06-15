"""Fractal swing, KL divergence, BUY/HOLD/SELL rule engine."""

from __future__ import annotations

import numpy as np
import polars as pl
from scipy.stats import entropy


def calc_fractal_swings(df: pl.DataFrame, col: str, omega: int = 3) -> pl.DataFrame:
    arr = df[col].to_numpy()
    is_swing_low = np.zeros(len(arr), dtype=bool)
    is_swing_high = np.zeros(len(arr), dtype=bool)

    for i in range(omega, len(arr) - omega):
        window = arr[i - omega : i + omega + 1]
        center = arr[i]

        if center == np.min(window):
            is_swing_low[i] = True
        elif center == np.max(window):
            is_swing_high[i] = True

    return df.with_columns([
        pl.Series("is_swing_low", is_swing_low),
        pl.Series("is_swing_high", is_swing_high),
    ])


def calc_kl_divergence(p_dist: np.ndarray, s_dist: np.ndarray) -> float:
    p_norm = np.abs(p_dist) + 1e-9
    s_norm = np.abs(s_dist) + 1e-9

    p_prob = p_norm / np.sum(p_norm)
    s_prob = s_norm / np.sum(s_norm)

    return float(entropy(p_prob, s_prob))


def fractal_confirmed(row: dict) -> bool:
    """Swing low gần nhất xác nhận đáy (bullish divergence context)."""
    return bool(row.get("is_swing_low"))


def decide_action(
    alpha: float,
    safety: float,
    kl_div: float,
    *,
    fractal_ok: bool = False,
) -> str:
    """L-03: KL + fractal ảnh hưởng quyết định action."""
    if alpha > 60 and safety > 40:
        if kl_div > 0.5 and not fractal_ok:
            return "HOLD"
        return "BUY"
    if alpha < 40:
        return "SELL"
    return "HOLD"


def pick_signal_row(rows: list[dict]) -> dict:
    """Chọn row tín hiệu — ưu tiên BUY gần nhất trong 5 dòng cuối (khớp playground)."""
    tail = rows[-5:] if len(rows) >= 5 else rows
    for row in reversed(tail):
        alpha = float(row["galaxy_alpha_score"])
        safety = float(row["galaxy_safety_score"])
        if alpha > 60 and safety > 40:
            return row
    return rows[-1]
