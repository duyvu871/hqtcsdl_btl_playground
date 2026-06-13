"""Engine phát hiện phân kỳ (Divergence) và sinh tín hiệu."""

from __future__ import annotations

def detect_signal(price_change_pct: float, sentiment_change: float) -> tuple[str, str]:
    """
    Trả về (Hành động, Lý do) dựa trên logic Divergence.
    Ngưỡng (Threshold): 
    - Giá biến động đáng kể khi |price_change_pct| > 0.005 (0.5%)
    - Sentiment thay đổi đáng kể khi |sentiment_change| > 0.2
    """
    p_change = price_change_pct
    s_change = sentiment_change
    
    # Ngưỡng nhạy cảm (có thể tinh chỉnh thành tham số cấu hình)
    S_THRESHOLD = 0.2 
    P_THRESHOLD = 0.005 

    # 1. Bullish Divergence (Phân kỳ dương)
    # Giá giảm hoặc đi ngang, nhưng Sentiment tăng mạnh -> Gom hàng (Smart money)
    if p_change <= P_THRESHOLD and s_change >= S_THRESHOLD:
        return "BUY", "Bullish Divergence (Giá giảm/sideway nhưng Social Sentiment tăng mạnh)"

    # 2. Bearish Divergence (Phân kỳ âm)
    # Giá tăng mạnh, nhưng Sentiment giảm/FUD -> Phân phối đỉnh
    if p_change >= P_THRESHOLD and s_change <= -S_THRESHOLD:
        return "SELL", "Bearish Divergence (Giá tăng nhưng Sentiment suy yếu / FUD)"

    # 3. Confirmation (Thuận chiều tăng)
    if p_change > 0 and s_change > 0:
        return "HOLD", "Confirmation (Giá tăng, Sentiment tăng thuận chiều)"

    # 4. Capitulation (Bán tháo)
    if p_change < 0 and s_change < 0:
        return "WAIT", "Capitulation (Hoảng loạn, chờ đợi tín hiệu rõ ràng hơn)"

    return "HOLD", "Neutral (Không có đột biến từ Social/Market)"