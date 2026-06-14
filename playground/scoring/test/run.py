#!/usr/bin/env python3
"""
Nhạc trưởng Giả lập v2.1 - Chạy đối soát thuật toán theo từng Test Case lựa chọn.

===================================================================================
HƯỚNG DẪN KÍCH HOẠT KIỂM THỬ TRÊN TERMINAL (CLI USAGE GUIDE)
===================================================================================
Để kiểm thử các kịch bản thị trường khác nhau, bạn mở Terminal tại thư mục 
gốc của mô-đun ('playground/scoring/') và thực thi các lệnh tương ứng sau:

1. Kiểm thử Phân kỳ dương (Bullish Divergence - Gom hàng bắt đáy):
   $ uv run python test/run.py --case bullish_divergence
   --> Ý nghĩa: Giả lập giá sập tạo FUD nhưng mạng xã hội/cá mập âm thầm gom hàng.
   --> Kỳ vọng: Alpha Score tăng độc lập, hệ thống kích hoạt tín hiệu [BUY].

2. Kiểm thử Phân kỳ âm (Bearish Divergence - Bẫy tăng giá Bull Trap):
   $ uv run python test/run.py --case bearish_divergence
   --> Ý nghĩa: Giả lập giá tăng tạo FOMO ảo nhưng dòng tiền mạng xã hội đã rút lui.
   --> Kỳ vọng: H_t gãy pha xu hướng, hệ thống bẻ lái phát tín hiệu [SELL].

3. Kiểm thử Biến động hoảng loạn (High Volatility Panic - Dao rơi tự do):
   $ uv run python test/run.py --case high_volatility_panic
   --> Ý nghĩa: Thị trường sập mạnh theo parabol, tâm lý đám đông hoảng loạn tột độ.
   --> Kỳ vọng: Volatility Z-Score cực đại ép CARA Penalty sụt về sát 0. 
                Safety Score bị triệt tiêu hoàn toàn, khóa chặt vị thế [HOLD].
===================================================================================
"""

import sys
import argparse
from pathlib import Path

# Đăng ký thư mục gốc 'scoring' vào PATH hệ thống để nhận diện thư mục 'lib'
_SCORING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCORING_DIR))

import polars as pl
from rich.console import Console
from rich.table import Table
from datetime import datetime

# Import các hàm biến đổi toán học cuốn từ thư viện lõi
from lib.transformer import calc_log_return, calc_rolling_zscore, calc_rolling_ols_slope, calc_cara_penalty
from lib.ortho import orthogonalize_momentum
from lib.rules import calc_fractal_swings
from lib.score import calculate_dual_scores
from lib.mock_data_v2 import get_mock_scenario

def main():
    # 1. Khởi tạo bộ đọc tham số dòng lệnh (CLI Arguments)
    parser = argparse.ArgumentParser(description="Galaxy Score v2.1 Simulator")
    parser.add_argument(
        "--case", 
        type=str, 
        default="bullish_divergence",
        choices=["bullish_divergence", "bearish_divergence", "high_volatility_panic"],
        help="Lựa chọn kịch bản dữ liệu giả lập để test"
    )
    args = parser.parse_args()
    console = Console()
    
    console.print(f"[bold yellow]🧪 MÔI TRƯỜNG KIỂM THỬ THUẬT TOÁN - TEST CASE: {args.case.upper()}[/bold yellow]")
    
    # 2. Bốc dữ liệu thô từ Mock Data Source tương ứng dựa trên cấu hình tham số nhập vào
    raw_data = get_mock_scenario(scenario_id=args.case, rows=48)
    df = pl.DataFrame(raw_data)
    
    # 3. THỰC THI CHUỖI TOÁN HỌC MA TRẬN CUỐN (WINDOW = 12 CORES)
    df = calc_log_return(df, "close")
    df = calc_rolling_zscore(df, "close_log_return", 12)
    df = calc_rolling_ols_slope(df, "close", 12)
    df = calc_rolling_zscore(df, "close_ols_slope", 12)
    
    # Đo lường biến động thực tế phục vụ hàm phạt rủi ro
    df = df.with_columns(pl.col("close_log_return").rolling_std(12).alias("volatility"))
    df = calc_rolling_zscore(df, "volatility", 12)
    df = calc_cara_penalty(df, "volatility_zscore", 1.2)
    
    # Lượng hóa và phân phối đặc trưng cấu trúc mạng xã hội
    df = calc_rolling_zscore(df, "sentiment_score", 12)
    df = df.with_columns(pl.col("social_volume").diff().alias("velocity_social"))
    df = df.with_columns((pl.col("social_volume") * pl.col("velocity_social")).alias("impact_raw"))
    df = calc_rolling_zscore(df, "impact_raw", 12).rename({"impact_raw_zscore": "Z_impact"})
    
    # Khử cộng tuyến bằng PCA trực giao và tính toán Dual-Score đầu ra
    df = orthogonalize_momentum(df, ["close_log_return_zscore", "close_ols_slope_zscore"])
    df = calculate_dual_scores(df)
    df = calc_fractal_swings(df, "close", 3)
    
    # 4. IN BẢNG BÁO CÁO KẾT QUẢ ĐẦU RA (RICH VISUALIZATION)
    table = Table(title=f"\nBảng Đối Soát Chỉ Số - Kết Quả {args.case}")
    table.add_column("Khung Giờ", style="cyan", justify="center")
    table.add_column("Giá Giả Lập", style="bold white", justify="right")
    table.add_column("CARA Penalty", style="red", justify="right")
    table.add_column("Alpha Score", style="bold magenta", justify="center")
    table.add_column("Safety Score", style="bold green", justify="center")
    table.add_column("Tín Hiệu Hệ Thống", style="bold white", justify="center")
    
    # Loại bỏ vùng biên khuyết NaN (11 dòng đầu) và trích xuất 5 dòng trạng thái cuối cùng để đối soát
    for row in df.drop_nulls().tail(5).to_dicts():
        dt_str = datetime.fromtimestamp(row["timestamp"]).strftime("%m-%d %H:%M")
        
        # Định dạng hành động dựa theo logic ranh giới điểm quy định trong thiết kế
        action_style = "[yellow]HOLD[/yellow]"
        if row["galaxy_alpha_score"] > 60 and row["galaxy_safety_score"] > 40:
            action_style = "[bold bg_green] BUY [/bold bg_green]"
        elif row["galaxy_alpha_score"] < 40:
            action_style = "[bold bg_red] SELL [/bold bg_red]"
            
        table.add_row(
            dt_str,
            f"${row['close']:,.1f}",
            f"{row['cara_penalty']:.4f}",
            f"{row['galaxy_alpha_score']:.1f}/100",
            f"{row['galaxy_safety_score']:.1f}/100",
            action_style
        )
    console.print(table)

if __name__ == "__main__":
    main()