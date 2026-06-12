# Module: Influence Weighting 

Đây là module thuộc Speed Layer của Hệ thống Dự đoán Crypto (MVP). 
Nhiệm vụ: Tính toán điểm ảnh hưởng (Influence Score) của người dùng mạng xã hội dựa trên thuật toán Log-Log Behavior Finance để chống Bot/Shill.

## Luồng dữ liệu (Data Contract)
- **Input:** Đọc Raw Event JSON từ Kafka topic `topic_raw_events`.
- **Output:** Lưu chuỗi JSON chứa điểm uy tín vào Redis để module Sentiment và Scoring Engine truy xuất.

## Cài đặt & Chạy Local
Module sử dụng `uv` để quản lý package.

1. Setup môi trường: `uv sync`
2. Đổi tên file `.env.example` thành `.env` và cấu hình IP Kafka/Redis.
3. Khởi động Worker: `uv run main.py`