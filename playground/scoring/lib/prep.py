"""Xử lý dữ liệu (Data Prep) bằng Polars."""

from __future__ import annotations
import polars as pl

def prepare_scoring_data(market_data: list[dict], social_data: list[dict]) -> pl.DataFrame:
    """Join Market & Social data, tính toán biến thiên (Delta)."""
    
    # Load list dict vào Polars DataFrame
    df_market = pl.DataFrame(market_data).with_columns(
        pl.col("timestamp").str.to_datetime()
    )
    df_social = pl.DataFrame(social_data).with_columns(
        pl.col("timestamp").str.to_datetime()
    )
    
    # Join 2 nhánh dữ liệu theo thời gian và mã coin
    df = df_market.join(df_social, on=["timestamp", "coin_id"], how="inner")
    
    # Sắp xếp theo thời gian để tính sự biến thiên so với giờ trước (lag)
    df = df.sort("timestamp")
    
    # Tính Delta P (Biến thiên giá) và Delta S (Biến thiên cảm xúc)
    df = df.with_columns(
        # (Close hiện tại - Close trước) / Close trước
        price_change_pct=(pl.col("close") - pl.col("close").shift(1)) / pl.col("close").shift(1),
        
        # Sentiment hiện tại - Sentiment trước
        sentiment_change=(pl.col("sentiment_score") - pl.col("sentiment_score").shift(1)),
        
        # (Social Vol hiện tại - Social Vol trước) / Social Vol trước
        vol_change_pct=(pl.col("social_volume") - pl.col("social_volume").shift(1)) / pl.col("social_volume").shift(1),
    )
    
    # Drop dòng đầu tiên vì không có dữ liệu quá khứ để tính lag
    return df.drop_nulls()