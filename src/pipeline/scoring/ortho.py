"""Trực giao hóa không gian nhân tố bằng PCA."""

from __future__ import annotations

import numpy as np
import polars as pl
from sklearn.decomposition import PCA


def orthogonalize_momentum(df: pl.DataFrame, feature_cols: list[str]) -> pl.DataFrame:
    if df.height == 0:
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))

    x_full = df.select(feature_cols).to_numpy()
    valid_mask_np = ~np.isnan(x_full).any(axis=1)
    x_clean = x_full[valid_mask_np]

    if len(x_clean) < 2:
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))

    try:
        pca = PCA(n_components=1)
        pc1 = pca.fit_transform(x_clean).flatten()

        ortho_series = np.full(df.height, np.nan)
        ortho_series[valid_mask_np] = pc1

        return df.with_columns(pl.Series("Z_momentum_ortho", ortho_series))
    except Exception:
        return df.with_columns(pl.lit(np.nan).alias("Z_momentum_ortho"))
