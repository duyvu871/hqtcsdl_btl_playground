"""Cấu trúc khởi tạo chỉ số hiển thị song song (Dual-Score)."""

import polars as pl

def calculate_dual_scores(df: pl.DataFrame, w1: float=0.4, w2: float=0.4, w3: float=0.2) -> pl.DataFrame:
    """
    H_t = w1*Z_momentum + w2*Z_sentiment + w3*Z_impact
    Alpha Score = 100 * Sigmoid(H_t)
    Safety Score = Alpha Score * CARA Penalty
    """
    # 1. Tính điểm sức khỏe cơ sở (H_t)
    df = df.with_columns(
        (
            w1 * pl.col("Z_momentum_ortho") + 
            w2 * pl.col("sentiment_score_zscore") + 
            w3 * pl.col("Z_impact")
        ).alias("H_t")
    )
    
    # 2. Galaxy Alpha Score (Hàm Sigmoid Nén)
    df = df.with_columns(
        (100.0 / (1.0 + (-pl.col("H_t")).exp())).alias("galaxy_alpha_score")
    )
    
    # 3. Galaxy Safety Score (Tích hợp hàm phạt CARA)
    # Lọc Null để tránh lỗi toán học, thay CARA bằng 1 nếu thiếu
    cara = pl.when(pl.col("cara_penalty").is_not_null()).then(pl.col("cara_penalty")).otherwise(1.0)
    
    df = df.with_columns(
        (pl.col("galaxy_alpha_score") * cara).alias("galaxy_safety_score")
    )
    
    return df