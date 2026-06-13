"""Tính toán Galaxy Score (Thang điểm 0 - 100)."""

from __future__ import annotations

def calculate_galaxy_score(
    sentiment_score: float, 
    vol_change_pct: float, 
    signal_action: str
) -> float:
    """
    Công thức MVP (Giả định):
    - Base score: 50
    - Sentiment (-1 đến 1) đóng góp tối đa ±25 điểm
    - Social Volume bùng nổ đóng góp tối đa +15 điểm
    - Tín hiệu BUY từ Divergence thưởng +10 điểm, SELL trừ -10 điểm
    """
    score = 50.0
    
    # 1. Trọng số Cảm xúc
    score += (sentiment_score * 25.0)
    
    # 2. Trọng số Khối lượng thảo luận (Social Volume)
    # Nếu volume tăng 50% (0.5), cộng 7.5 điểm. Tối đa cộng 15.
    vol_bonus = min(vol_change_pct * 15.0, 15.0)
    if vol_bonus > 0:
        score += vol_bonus
        
    # 3. Điểm thưởng/phạt từ Tín hiệu Phân kỳ
    if signal_action == "BUY":
        score += 10.0
    elif signal_action == "SELL":
        score -= 10.0
        
    # Chuẩn hóa về thang 0-100
    return max(0.0, min(100.0, score))