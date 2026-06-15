"""Galaxy Alpha / Safety dual-score."""

from __future__ import annotations

import polars as pl


def calculate_dual_scores(df: pl.DataFrame, w1: float = 0.4, w2: float = 0.4, w3: float = 0.2) -> pl.DataFrame:
    df = df.with_columns(
        (
            w1 * pl.col("Z_momentum_ortho")
            + w2 * pl.col("sentiment_score_zscore")
            + w3 * pl.col("Z_impact")
        ).alias("H_t")
    )

    df = df.with_columns(
        (100.0 / (1.0 + (-pl.col("H_t")).exp())).alias("galaxy_alpha_score")
    )

    cara = pl.when(pl.col("cara_penalty").is_not_null()).then(pl.col("cara_penalty")).otherwise(1.0)

    df = df.with_columns(
        (pl.col("galaxy_alpha_score") * cara).alias("galaxy_safety_score")
    )

    return df
