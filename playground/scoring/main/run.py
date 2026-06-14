#!/usr/bin/env python3
"""
Pipeline Stage 6 - Galaxy Score v2.1 (Production End-to-End Flow)
Tích hợp ghi dữ liệu tín hiệu đầu ra vào MongoDB theo thiết kế chuẩn mẫu hệ thống.
"""

import sys
from pathlib import Path

# Đăng ký thư mục gốc 'scoring' vào hệ thống PATH để nhận diện thư mục 'lib'
_SCORING_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SCORING_DIR))

import json
import uuid
import polars as pl
from rich.console import Console

# Import thuật toán định lượng dùng chung
from lib.transformer import calc_log_return, calc_rolling_zscore, calc_rolling_ols_slope, calc_cara_penalty
from lib.ortho import orthogonalize_momentum
from lib.rules import calc_fractal_swings, calc_kl_divergence
from lib.score import calculate_dual_scores

# Import các công cụ kết nối và điều phối Database từ lib tập trung
from lib.market import fetch_market_ohlcv
from lib.mongo import fetch_sentiment_metrics, get_signal_collection, ensure_indexes, insert_signals

def main():
    console = Console()
    console.print("[bold green]🚀 KHỞI CHẠY GALAXY SCORE™ v2.1 PRODUCTION PIPELINE[/bold green]")
    
    # 1. Kéo dữ liệu thực tế từ Binance và MongoDB (Kết quả Bước 4 & 5)
    market_list = fetch_market_ohlcv("BTC/USDT", "1h", 48)
    social_list = fetch_sentiment_metrics("BTC", "1h", 48)
    
    if not market_list or not social_list:
        console.print("[bold red]❌ Thất bại: Thiếu dữ liệu đầu vào. Pipeline dừng hoạt động.[/bold red]")
        return
        
    # 2. Khởi tạo Polars DataFrame và đồng bộ hóa chuỗi thời gian qua Inner Join
    df = pl.DataFrame(market_list).join(pl.DataFrame(social_list), on="timestamp", how="inner").sort("timestamp")
    
    if df.height < 15:
        console.print("[bold yellow]⚠️ Không đủ dữ liệu khớp mốc thời gian để chạy rolling window.[/bold yellow]")
        return

    # 3. TRÍCH XUẤT NHÂN TỐ & CHUẨN HÓA Z-SCORE (WINDOW = 12)
    df = calc_log_return(df, "close")
    df = calc_rolling_zscore(df, "close_log_return", 12)
    df = calc_rolling_ols_slope(df, "close", 12)
    df = calc_rolling_zscore(df, "close_ols_slope", 12)
    
    # Tính toán biến động thực tế (Volatility) để chuẩn bị cho hàm phạt rủi ro CARA
    df = df.with_columns(pl.col("close_log_return").rolling_std(12).alias("volatility"))
    df = calc_rolling_zscore(df, "volatility", 12)
    df = calc_cara_penalty(df, "volatility_zscore", 1.2)
    
    # Lượng hóa các đặc trưng lan truyền mạng xã hội
    df = calc_rolling_zscore(df, "sentiment_score", 12)
    df = df.with_columns(pl.col("social_volume").diff().alias("velocity_social"))
    df = df.with_columns((pl.col("social_volume") * pl.col("velocity_social")).alias("impact_raw"))
    df = calc_rolling_zscore(df, "impact_raw", 12).rename({"impact_raw_zscore": "Z_impact"})
    
    # 4. TRỰC GIAO HÓA MOMENTUM (PCA) KHỬ CỘNG TUYẾN
    df = orthogonalize_momentum(df, ["close_log_return_zscore", "close_ols_slope_zscore"])
    
    # 5. TÍNH ĐIỂM DUAL-SCORE (GALAXY ALPHA & SAFETY SCORE)
    df = calculate_dual_scores(df)
    
    # 6. ĐỘNG CƠ PHÂN KỲ FRACTAL (Xác thực trễ không thiên kiến)
    df = calc_fractal_swings(df, "close", 3)
    
    # Tính khoảng cách Kullback-Leibler Divergence (Cho 12 nến gần nhất)
    recent_p, recent_s = df["close"].tail(12).to_numpy(), df["sentiment_score"].tail(12).to_numpy()
    kl_div = calc_kl_divergence(recent_p, recent_s)
    
    # Loại bỏ các giá trị biên Null phát sinh do sai số pha cuốn trước khi bốc tách dòng cuối
    latest_rows = df.drop_nulls()
    if latest_rows.height == 0:
        console.print("[bold red]❌ Lỗi hệ thống: Ma trận trống sau khi tính toán phân kỳ.[/bold red]")
        return
        
    latest = latest_rows.tail(1).to_dicts()[0]
    
    # 7. ĐÓNG GÓI HỢP ĐỒNG DỮ LIỆU ĐẦU RA (DATA CONTRACT PAYLOAD)
    payload = {
        "signal_id": str(uuid.uuid4()),
        "coin_id": latest["coin_id"],
        "timeframe": "1h",
        "action": "BUY" if latest["galaxy_alpha_score"] > 60 and latest["galaxy_safety_score"] > 40 else "HOLD",
        "metrics": {
            "galaxy_alpha_score": round(latest["galaxy_alpha_score"], 2),
            "galaxy_safety_score": round(latest["galaxy_safety_score"], 2),
            "kl_divergence": round(kl_div, 4),
            "confidence": round(100 - (kl_div * 10), 2)
        },
        "execution": {
            "target_price": round(latest["close"] * 1.05, 2),
            "stop_loss": round(latest["close"] * 0.98, 2)
        },
        "timestamp": int(latest["timestamp"])
    }
    
    console.print("\n[bold green]JSON Data Contract Lượng Hóa:[/bold green]")
    console.print(json.dumps(payload, indent=2))

    # 8. THỰC THI GHI DỮ LIỆU VÀO MONGODB (ĐỒNG BỘ THEO MẪU STAGE 2)
    signal_col = get_signal_collection()
    ensure_indexes(signal_col) # Đảm bảo hạ tầng index unique chống trùng lặp dữ liệu
    
    inserted, skipped = insert_signals(signal_col, [payload])
    
    if inserted > 0:
        console.print(f"\n[bold bg_green] ✅ Ghi MongoDB thành công: Đã lưu tín hiệu {payload['signal_id']} vào bảng! [/bold bg_green]")
    elif skipped > 0:
        console.print("\n[bold yellow] ⚠️ Tín hiệu bị bỏ qua: Trùng lặp khóa Unique Key trong Database. [/bold yellow]")

if __name__ == "__main__":
    main()