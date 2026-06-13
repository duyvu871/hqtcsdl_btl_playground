#!/usr/bin/env python3
"""
Pipeline Stage 6 — Proprietary Scoring (Rule-based Divergence)

Chạy thử nghiệm với Mock Data:
  cd playground/scoring
  uv sync
  uv run python run.py
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

# Import logic nội bộ
from lib.mock_data import MOCK_MARKET_DATA, MOCK_SOCIAL_DATA
from lib.prep import prepare_scoring_data
from lib.rules import detect_signal
from lib.score import calculate_galaxy_score

def main():
    console = Console()
    console.print("[bold cyan]BẮT ĐẦU CHẠY PIPELINE BƯỚC 6 (SCORING)...[/bold cyan]\n")
    
    # 1. Chuẩn bị dữ liệu bằng Polars
    df = prepare_scoring_data(MOCK_MARKET_DATA, MOCK_SOCIAL_DATA)
    
    # 2. Khởi tạo bảng hiển thị kết quả
    table = Table(title="Signals & Galaxy Score™ (Rule-Based MVP)")
    table.add_column("Thời gian", justify="center", style="cyan")
    table.add_column("Giá", justify="right", style="green")
    table.add_column("Δ Giá (%)", justify="right")
    table.add_column("Δ Sentiment", justify="right")
    table.add_column("Signal", justify="center", style="bold")
    table.add_column("Galaxy Score", justify="center", style="bold yellow")
    table.add_column("Ghi chú (Lý do)", style="dim")

    # 3. Lặp qua từng khung thời gian để chấm điểm
    # Chuyển DataFrame thành list dict để xử lý từng dòng
    records = df.to_dicts()
    
    for row in records:
        ts = row["timestamp"].strftime("%Y-%m-%d %H:%M")
        price = f"${row['close']:,.0f}"
        p_change = row["price_change_pct"]
        s_change = row["sentiment_change"]
        v_change = row["vol_change_pct"]
        sentiment = row["sentiment_score"]
        
        # Gọi Rule Engine để lấy tín hiệu phân kỳ
        action, reason = detect_signal(p_change, s_change)
        
        # Gọi Score Engine để tính điểm sức khỏe mạng xã hội
        galaxy_score = calculate_galaxy_score(sentiment, v_change, action)
        
        # Format màu sắc cho trực quan
        p_str = f"[red]{p_change*100:.2f}%[/red]" if p_change < 0 else f"[green]+{p_change*100:.2f}%[/green]"
        s_str = f"[red]{s_change:+.2f}[/red]" if s_change < 0 else f"[green]{s_change:+.2f}[/green]"
        
        action_style = "green" if action == "BUY" else "red" if action == "SELL" else "yellow"
        action_formatted = f"[{action_style}]{action}[/{action_style}]"
        
        # Đưa vào bảng
        table.add_row(
            ts, 
            price, 
            p_str, 
            s_str, 
            action_formatted, 
            f"{galaxy_score:.1f}/100", 
            reason
        )

    console.print(table)
    console.print("\n[dim]Lưu ý: Dữ liệu đang được đọc từ biến giả lập trong `lib/mock_data.py`. "
                  "Sau khi hoàn thành Bước 4/5, có thể thay đổi `run.py` để trỏ vào MongoDB/CCXT.[/dim]")

if __name__ == "__main__":
    main()