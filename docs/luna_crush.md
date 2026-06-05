Để tham khảo pipeline của **LunarCrush** (một trong những nền tảng dẫn đầu về "Social Intelligence" cho Crypto), bạn cần nhìn vào cách họ xử lý hàng tỷ điểm dữ liệu từ mạng xã hội và kết hợp chúng với dữ liệu thị trường theo thời gian thực.

> **Luồng dữ liệu chi tiết (sơ đồ, contract từng bước):** xem [`docs/lunacrush-data-flow.md`](lunacrush-data-flow.md).

Dưới đây là phân tích chi tiết pipeline của họ theo phong cách "reverse-engineering" dành cho đội ngũ kỹ thuật:

---

## 1. Kiến trúc Tổng quan: Hybrid Lambda Architecture

LunarCrush xử lý dữ liệu theo mô hình **Lambda Architecture** để giải quyết bài toán: vừa phải có kết quả real-time (Speed Layer) vừa phải đảm bảo độ chính xác tuyệt đối và dữ liệu lịch sử (Batch Layer).

* **Speed Layer (Real-time):** Xử lý các luồng Twitter/X, Telegram, Reddit ngay khi chúng xuất hiện để tính toán "Social Velocity" (tốc độ lan truyền).
* **Batch Layer:** Chạy định kỳ để "clean" dữ liệu, loại bỏ spam phức tạp mà các model real-time bỏ lỡ, và tính toán lại các chỉ số như **Galaxy Score™** dựa trên các cửa sổ thời gian lớn hơn (24h, 7d).

## 2. Chi tiết Pipeline 6 bước của LunarCrush

### Bước 1: Raw Collection (Đa nguồn & Đa ngôn ngữ)

* Họ không chỉ lấy nội dung post, mà lấy toàn bộ: **Likes, Shares, Comments, số lượng Followers của người đăng, và metadata của link đính kèm**.
* **Tech stack gợi ý:** Sử dụng một cụm Worker (Python) dùng `Playwright` hoặc API chính thức của các sàn/mạng xã hội, đẩy vào **Kafka** hoặc **RabbitMQ**.

### Bước 2: AI Noise & Spam Filtering (Lọc nhiễu)

Đây là "vũ khí bí mật" của họ.

* Họ sử dụng **Machine Learning** để phân biệt giữa "Organic buzz" (người dùng thật thảo luận) và "Bot hype" (shill lệnh tự động).
* **Feature Engineering ở đây:** Tần suất post của user, tỷ lệ tương tác/followers, độ tương đồng của nội dung (duplicate content detection).

### Bước 3: Entity Recognition & Mapping (Định danh)

* Hệ thống phải hiểu một tweet như *"I love $BTC and the new updates on Ethereum"* thuộc về cả hai thực thể: Bitcoin và Ethereum.
* **AI Model:** Dùng **NER (Named Entity Recognition)** để map từ khóa, hashtag vào ID của từng đồng coin trong database.

### Bước 4: Sentiment Analysis (Phân tích cảm xúc)

* Họ không chỉ phân loại Tích cực/Tiêu cực mà còn tính toán **Sentiment Strength** (Độ mạnh của cảm xúc).
* **Model:** Sử dụng các Transformer như **RoBERTa** hoặc **FinBERT** đã được fine-tune trên dữ liệu Crypto để hiểu được các tiếng lóng như "to the moon", "rekt", "wagmi".

### Bước 5: Influence Weighting (Trọng số ảnh hưởng)

* LunarCrush áp dụng nguyên tắc: **Một tweet từ Elon Musk có giá trị hơn 10.000 tweet từ các tài khoản mới lập**.
* Mỗi tương tác được nhân với một hệ số "Influence Score" của người tạo nội dung đó trước khi đưa vào bộ lọc tính điểm.

### Bước 6: Proprietary Scoring (Tính điểm độc quyền)

Cuối cùng, họ kết hợp dữ liệu Social với Market Data (từ Binance) để tạo ra:

* **Galaxy Score™:** Tính toán độ lệch (divergence) giữa giá và cảm xúc. Ví dụ: Giá giảm nhưng Social Sentiment tăng mạnh $\rightarrow$ Tín hiệu mua tiềm năng.

---

## 3. Reference Architecture cho Team của bạn (CTO-level)

Dựa trên việc bạn đang dùng **NestJS, Python và Transformers**, đây là cách "lắp ghép" pipeline lấy cảm hứng từ LunarCrush:

### Tầng Hạ tầng (Infrastructure)

* **Data Ingestion:** Sử dụng **Cloudflare Workers** (giống LunarCrush hiện tại) để nhận Webhook từ mạng xã hội hoặc làm Proxy crawl dữ liệu để giảm chi phí băng thông và tăng tốc độ xử lý tại Edge.
* **Storage:**
* **Redis:** Lưu trữ các Feature real-time (số lượng tweet trong 5 phút qua).
* **TimescaleDB (PostgreSQL):** Lưu dữ liệu nến và sentiment lịch sử để train model.



### Tầng AI (Inference)

* **Sentiment Branch:** Chạy một microservice Python (FastAPI) load model **FinBERT**.
* **Prediction Branch:** Chạy model **Temporal Fusion Transformer (TFT)** để nhận đầu vào là (Giá + Social Sentiment + Social Volume) và output là gợi ý đầu tư.

### Tầng Logic (Orchestrator)

* **NestJS:** Đóng vai trò điều phối. Khi có dữ liệu mới từ Binance (qua WebSocket), NestJS sẽ "hỏi" Redis xem Sentiment hiện tại là bao nhiêu, sau đó gọi sang AI Service để lấy dự đoán và đẩy qua Telegram Bot cho bạn.

---

**Lời khuyên:** Đừng cố xây dựng một hệ thống quá phức tạp ngay lập tức. Hãy bắt đầu bằng việc:

1. Lấy dữ liệu giá Binance (Real-time).
2. Lấy dữ liệu từ một nguồn Social (X/Twitter).
3. Dùng một model Sentiment cơ bản để tính điểm trung bình mỗi giờ.
4. Cộng hai chỉ số này lại để xem có sự tương quan (Correlation) không trước khi đưa Transformer vào "deep dive".