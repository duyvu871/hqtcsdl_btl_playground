# Stage 5 — Influence Weighting

Module tính toán trọng số uy tín (Influence Score) cho hệ thống Crypto Social Prediction Pipeline.

## Mục đích
Đánh giá độ uy tín và sức ảnh hưởng của một tài khoản mạng xã hội dựa trên mô hình **Log-Log Behavior Finance**. Module này giúp hệ thống lọc bỏ bot/shill account và khuếch đại tín hiệu từ các Mega-Whales (Cá voi) hoặc KOLs thật sự trong thị trường Crypto.

## Pipeline Stage
- Stage 1: Raw Collection
- Stage 2: Spam / Noise Filter
- Stage 3: NER / Coin Mapping
- Stage 4: Sentiment Analysis 
- **Stage 5: Influence Weighting ← MODULE NÀY**
- Stage 6: Scoring / Prediction

## Giao thức Dữ liệu (Data Contract)

### Input (Luồng Kafka Consumer)
Lắng nghe từ Topic: `topic_raw_events` (hoặc cấu hình qua biến môi trường).
Định dạng JSON yêu cầu từ **Module Raw Collection (Stage 1)**:

```json
{
  "event_id": "uuid",
  "author_id": "user_123",
  "source": "twitter",
  "clean_text": "Buy BTC now to the moon",
  "is_verified": true,
  "metrics": {
    "followers": 150000,
    "likes": 2000,
    "retweets": 350,
    "replies": 120
  },
  "timestamp": 1716110997
}
```

### Output (Lưu trữ Redis Cache)
Lưu kết quả điểm số vào Redis để các module tiếp theo (như **Scoring Engine - Stage 6**) truy xuất với độ trễ thấp (Low-latency).
- **Key cấu trúc:** `author_auth:{author_id}`
- **Thời gian tồn tại (TTL):** 7 ngày (604800 giây) - Tự động xóa để tối ưu RAM.
- **Value (JSON Format):**

```json
{
  "author_id": "user_123",
  "influence_score": 35.8452,
  "updated_at": 1716111005
}
```

## Cơ sở Lý thuyết (Theoretical Foundation)

Mô hình chấm điểm uy tín của hệ thống được xây dựng dựa trên 3 nền tảng lý thuyết chính trong Phân tích Dữ liệu lớn (Big Data Analytics) và Tài chính Hành vi (Behavioral Finance):

1. **Phân phối Lũy thừa trong Mạng xã hội (Power-Law Distribution):**
   Trong môi trường mạng xã hội Crypto, lượng người theo dõi (Followers) không phân bố đồng đều theo hàm tuyến tính mà tuân theo quy luật lũy thừa (số ít tài khoản nắm giữ lượng tương tác khổng lồ). Nếu sử dụng hàm tuyến tính thông thường, các tài khoản lớn sẽ làm biến dạng toàn bộ thang điểm và áp đảo hoàn toàn các tài khoản khác. Hàm Logarit cơ số 10 (`log10`) được áp dụng để "bình chuẩn hóa" (normalize) độ lệch này, giúp thu hẹp khoảng cách dữ liệu mà vẫn giữ được tính thứ bậc.

2. **Quy luật Weber-Fechner (Độ nhạy biên giảm dần):**
   Lý thuyết này chỉ ra rằng: Sự khác biệt giữa 10 followers và 1,000 followers là cực kỳ lớn và mang tính đột biến. Nhưng sự khác biệt giữa 1,000,000 followers và 1,001,000 followers lại không mang nhiều ý nghĩa về mặt tăng trưởng sức ảnh hưởng. Hàm Logarit mô phỏng chính xác sự "giảm dần giá trị biên" này của tâm lý học hành vi.

3. **Mô hình Tương tác kép (Dual-Metric Validation):**
   Để hạn chế tối đa vấn đề tài khoản ảo (Bot/Shill) mua followers giả lập tương tác, mô hình bắt buộc phải tích hợp đồng thời cả số lượng người theo dõi và tương tác thực tế (`Total_Engagement`). Một tài khoản có hàng triệu followers nhưng các bài viết không có lượt tương tác (Likes, Retweets) sẽ bị thuật toán dìm điểm do vế tương tác tiến về 0. Ngược lại, hệ thống ghi nhận và cộng điểm thưởng cho các tài khoản chính chủ đã được xác thực danh tính (`is_verified`).

## Giải thích Thuật toán (Log-Log Model)

Hệ thống áp dụng hàm Logarit cơ số 10 dựa trên cơ sở lý thuyết phía trên để chuẩn hóa dữ liệu đầu vào:

**Công thức lõi:**
```text
Score = log10(Followers + 1) * log10(Total_Engagement + 1) * Bonus
```

**Trong đó:**
- `Total_Engagement` = Likes + Retweets + Replies
- `Bonus` = 1.5 (Nếu tài khoản có tick xanh / `is_verified` là `true`), ngược lại là 1.0.

**Thang điểm đánh giá nội bộ:**
- `Score > 30`: 🐳 Mega-Whale (Siêu cá voi)
- `Score > 10`: 🔥 Siêu uy tín (KOL/Viral)
- `Score > 5` : ✅ Uy tín (Organic tốt)
- `Score < 5` : 🗑️ Rác / Tương tác ảo (Bot)

## Cài đặt & Chạy Local

Sử dụng `uv` để quản lý môi trường và thư viện siêu tốc:

1. Cài đặt dependencies và đồng bộ môi trường:
```bash
uv sync
```

2. Khởi tạo cấu hình nội bộ:
```bash
cp .env.example .env
```

### Cấu hình .env
```ini
REDIS_HOST=localhost
REDIS_PORT=6379
KAFKA_BROKER=localhost:9092
KAFKA_TOPIC_INPUT=topic_raw_events
```

### Cách chạy
Khởi chạy Module ở chế độ Production (Lắng nghe Kafka 24/7):
```bash
uv run main.py
```

## Cấu trúc Module
```text
playground/influence/
├── README.md            ← Tài liệu hướng dẫn này
├── main.py              ← Service chạy luồng chính (Kafka Consumer & Thuật toán)
├── pyproject.toml       ← Danh sách thư viện (confluent-kafka, redis, python-dotenv)
├── uv.lock              ← Khóa phiên bản thư viện
└── .env.example         ← Template chứa các biến môi trường
```