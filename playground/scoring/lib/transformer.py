"""Biến đổi toán học, chuẩn hóa Z-Score và trích xuất nhân tố."""

import polars as pl
import numpy as np
from numpy.lib.stride_tricks import sliding_window_view

def calc_log_return(df: pl.DataFrame, col: str = "close") -> pl.DataFrame:
    """Tỷ suất sinh lời logarit: R_t = ln(P_t / P_{t-1})"""
    return df.with_columns(
        pl.col(col).log().diff().alias(f"{col}_log_return")
    )

def calc_rolling_zscore(df: pl.DataFrame, col: str, window: int = 24) -> pl.DataFrame:
    """Chuẩn hóa Z-Score: Z_t = (X_t - mu_t) / sigma_t"""
    mean_col = pl.col(col).rolling_mean(window_size=window)
    std_col = pl.col(col).rolling_std(window_size=window)
    
    return df.with_columns(
        ((pl.col(col) - mean_col) / std_col).alias(f"{col}_zscore")
    )

def calc_rolling_ols_slope(df: pl.DataFrame, col: str, window: int = 24) -> pl.DataFrame:
    """
    Tính hệ số góc OLS trượt bằng NumPy sliding_window_view để tối ưu tốc độ.
    T_t = m = Cov(X, Y) / Var(X)
    """
    arr = df[col].to_numpy()
    if len(arr) < window:
        return df.with_columns(pl.lit(None).cast(pl.Float64).alias(f"{col}_ols_slope"))
        
    windows = sliding_window_view(arr, window_shape=window)
    x = np.arange(window)
    x_mean = x.mean()
    x_var = x.var()
    
    # Tính OLS Slope vectorized cho mọi cửa sổ
    y_mean = np.mean(windows, axis=1, keepdims=True)
    cov = np.mean((x - x_mean) * (windows - y_mean), axis=1)
    slopes = cov / x_var
    
    # Pad mảng kết quả với NaN ở các dòng đầu tiên
    padded_slopes = np.pad(slopes, (window - 1, 0), constant_values=np.nan)
    
    return df.with_columns(pl.Series(f"{col}_ols_slope", padded_slopes))

def calc_cara_penalty(df: pl.DataFrame, vol_col: str, lambda_risk: float = 1.0) -> pl.DataFrame:
    # THÊM chữ r ở đầu chuỗi để sửa lỗi SyntaxWarning độc giả LaTeX \lambda
    r"""
    Hàm phạt biến động rủi ro hàm mũ CARA chuẩn hóa: R_t = exp(-\lambda * Z_{vol,t})
    Bọc màng lọc an toàn để hệ số phạt TUYỆT ĐỐI chỉ nằm trong khoảng (0, 1].
    """
    return df.with_columns(
        # SỬA LỖI TẠI ĐÂY: Dùng upper_bound=1.0 thay cho max_val=1.0 theo chuẩn Polars mới
        (-lambda_risk * pl.col(vol_col)).exp().clip(upper_bound=1.0).alias("cara_penalty")
    )