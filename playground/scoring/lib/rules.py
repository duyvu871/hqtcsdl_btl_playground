"""Động cơ phát hiện phân kỳ thống kê phi huấn luyện."""

import polars as pl
import numpy as np
from scipy.stats import entropy

def calc_fractal_swings(df: pl.DataFrame, col: str, omega: int = 3) -> pl.DataFrame:
    """
    Xác định Swing High/Low có độ trễ xác thực Fractal (T - \omega).
    Khắc phục hoàn toàn Look-Ahead Bias.
    """
    arr = df[col].to_numpy()
    is_swing_low = np.zeros(len(arr), dtype=bool)
    is_swing_high = np.zeros(len(arr), dtype=bool)
    
    # Chỉ duyệt đến len - omega để đảm bảo có đủ nến tương lai xác nhận
    for i in range(omega, len(arr) - omega):
        window = arr[i - omega : i + omega + 1]
        center = arr[i]
        
        if center == np.min(window):
            is_swing_low[i] = True
        elif center == np.max(window):
            is_swing_high[i] = True
            
    return df.with_columns([
        pl.Series("is_swing_low", is_swing_low),
        pl.Series("is_swing_high", is_swing_high)
    ])

def calc_kl_divergence(p_dist: np.ndarray, s_dist: np.ndarray) -> float:
    """
    Khoảng cách Kullback-Leibler: D_{KL}(P || S).
    Đo lường entropy thất thoát, dùng làm hệ số tự tin (Confidence Modifier).
    """
    # Xử lý mảng: Chuẩn hóa thành hàm mật độ xác suất (tổng = 1, giá trị > 0)
    p_norm = np.abs(p_dist) + 1e-9
    s_norm = np.abs(s_dist) + 1e-9
    
    p_prob = p_norm / np.sum(p_norm)
    s_prob = s_norm / np.sum(s_norm)
    
    return entropy(p_prob, s_prob)