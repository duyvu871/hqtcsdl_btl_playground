"""
Kho lưu trữ dữ liệu giả lập (Mock Data Source) cho Galaxy Score v2.1.
Cung cấp 3 kịch bản thị trường (Test Cases) chuẩn hóa đầu vào để đối soát thuật toán.
"""

import numpy as np
from datetime import datetime

def get_mock_scenario(scenario_id: str = "bullish_divergence", rows: int = 48) -> dict[str, list]:
    """
    Sinh dữ liệu chuỗi thời gian giả lập theo từng kịch bản cụ thể.
    
    Args:
        scenario_id: Loại kịch bản cần test:
            - 'bullish_divergence': Giá giảm FUD, Sentiment tăng gom hàng (Kỳ vọng: BUY)
            - 'bearish_divergence': Giá tăng FOMO, Sentiment sụt giảm (Kỳ vọng: SELL/HOLD)
            - 'high_volatility_panic': Thị trường sập mạnh, rủi ro cực cao (Kỳ vọng: HOLD)
        rows: Số lượng nến lịch sử (Mặc định 48 nến để đủ cửa sổ cuốn 12).
    """
    # Khởi tạo mốc thời gian chuẩn (Unix Timestamp) cho ngày hôm nay (2026-06-14)
    base_ts = datetime(2026, 6, 14, 0, 0).timestamp()
    rng = np.random.default_rng(42) # Khóa seed để dữ liệu test mang tính bất biến (Deterministic)
    
    # Khởi tạo mảng thời gian tăng dần 1 giờ
    timestamps = [base_ts + i * 3600 for i in range(rows)]
    coin_ids = ["BTC"] * rows
    
    # Cấu hình toán học cho từng kịch bản
    if scenario_id == "bullish_divergence":
        # CHUẨN 1: PHÂN KỲ DƯƠNG (BẮT ĐÁY)
        # Giá giảm đều từ 69,500 về 67,000 tạo FUD cắt lỗ
        prices = np.linspace(69500, 67000, rows) + np.sin(np.arange(rows)) * 80
        # Nhưng cá mập âm thầm mua vào -> Sentiment tăng vọt từ -0.3 lên +0.75
        sentiment = np.linspace(-0.3, 0.75, rows) + rng.normal(0, 0.04, rows)
        # Social Volume bùng nổ mạnh mẽ kèm răng cưa lớn để tạo lực đẩy Velocity
        social_volume = np.linspace(2000, 8500, rows) + np.sin(np.arange(rows) * 0.8) * 350 + rng.normal(0, 50, rows)
        market_volume = np.linspace(1500, 3500, rows)

    elif scenario_id == "bearish_divergence":
        # CHUẨN 2: PHÂN KỲ ÂM (FỒ MO ĐỈNH)
        # Giá đẩy mạnh từ 65,000 lên 72,000 tạo cảm giác tăng trưởng giả
        prices = np.linspace(65000, 72000, rows) + np.cos(np.arange(rows)) * 100
        # Nhưng dòng tiền xã hội nguội lạnh -> Sentiment tụt dốc từ 0.6 về -0.4
        sentiment = np.linspace(0.6, -0.4, rows) + rng.normal(0, 0.04, rows)
        # Cộng đồng mất tương tác, lượng bài viết giảm dần
        social_volume = np.linspace(6000, 1800, rows) + np.sin(np.arange(rows) * 0.5) * 200
        market_volume = np.linspace(4000, 1500, rows)

    elif scenario_id == "high_volatility_panic":
        # CHUẨN 3: HOẢNG LOẠN BIẾN ĐỘNG CAO (CRASH)
        # Giá sập cực mạnh theo hình parabol từ 68,000 về 59,000
        prices = 68000 - (np.arange(rows) ** 1.8) * 4.5
        # Sentiment hoảng loạn, nát bét ở vùng cực âm
        sentiment = np.linspace(0.1, -0.85, rows) + rng.normal(0, 0.08, rows)
        # Khối lượng xả hàng và bài thảo luận chửi bới bùng nổ điên cuồng
        social_volume = np.linspace(2000, 15000, rows) + rng.normal(0, 500, rows)
        market_volume = np.linspace(1000, 9000, rows)
        
    else:
        raise ValueError(f"Không tồn tại kịch bản test case: {scenario_id}")

    # Khớp dịch dữ liệu thành cấu trúc Data Flow đầu vào chuẩn
    return {
        "timestamp": timestamps,
        "coin_id": coin_ids,
        "close": prices.tolist(),
        "volume": [float(v) for v in market_volume],
        "social_volume": np.maximum(10, social_volume).tolist(), # Giới hạn không bị âm volume
        "sentiment_score": sentiment.tolist()
    }