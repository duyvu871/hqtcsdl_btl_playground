# TÀI LIỆU KỸ THUẬT NỘI BỘ: HỆ THỐNG DỰ ĐOÁN CRYPTO (MVP)

**Version:** 1.1
**Date:** 19/05/2026
**Architecture Style:** Event-Driven Microservices (lấy cảm hứng Lambda Architecture của LunaCrush)
**Tham chiếu:** `docs/luna_crush.md`, `docs/lunacrush-data-flow.md`

---

## 1. GHI CHÚ GIẢ ĐỊNH (EXPLICIT ASSUMPTIONS)

* **Phạm vi MVP:** Chỉ track Top 10 coins (BTC, ETH, SOL, v.v.).
* **Khung thời gian (Timeframes):** Phân tích và dự đoán trên nến 15m và 1h.
* **Môi trường:** Triển khai MVP trên single-node Ubuntu server (có GPU hoặc tối ưu CPU cho Inference) trước khi scale lên Kubernetes.
* **Hệ sinh thái nội bộ:** Team sử dụng thành thạo Docker, NestJS, Python và Linux.

---

## 2. TỔNG QUAN KIẾN TRÚC PIPELINE

Hệ thống được thiết kế theo mô hình **Event-Driven Architecture**, sử dụng Message Broker làm xương sống để luân chuyển dữ liệu bất đồng bộ giữa các module xử lý (Workers). Thiết kế này là phiên bản đơn giản hóa của **Lambda Architecture** mà LunaCrush sử dụng để xử lý hàng tỷ điểm dữ liệu social + market.

| Tầng | Vai trò | Độ trễ | Output ví dụ |
| --- | --- | --- | --- |
| **Speed Layer** | Social Velocity, sentiment tức thì | Giây → phút | "BTC có 500 tweet/phút, sentiment +0.7" |
| **Batch/Storage Layer** | Làm sạch sâu, tính lại chỉ số dài hạn, retrain model | 15m → 24h | Galaxy Score, signal 1h, lịch sử dashboard |

* **Tốc độ (Speed Layer):** Dữ liệu Market (WebSockets) và Social (Scraping) được đẩy liên tục vào Broker, xử lý real-time để phục vụ model Inference.
* **Lưu trữ (Batch/Storage Layer):** Toàn bộ event sạch và kết quả dự đoán được lưu trữ Time-series để retrain model và hiển thị lịch sử trên Dashboard.
* **Ngôn ngữ chủ đạo:** Python cho Data/AI Workers; TypeScript (NestJS/Next.js) cho API/Orchestration và UI.

---

## 3. CƠ SỞ LÝ THUYẾT / NGUYÊN LÝ HOẠT ĐỘNG

* **Multimodal Prediction:** Biến động giá Crypto không chỉ phụ thuộc vào lịch sử giá (Technical Analysis) mà chịu tác động mạnh từ tâm lý đám đông (Social Sentiment). Sentiment social thường là **leading indicator** — dẫn giá ngắn hạn (15m–4h, tùy coin và volatility).
* **Information Diffusion:** Giá phản ánh cách thông tin lan truyền trên mạng xã hội. Engagement (likes, shares, comments) là proxy cho mức độ virality — không chỉ thu thập text mà cần cả metadata tương tác.
* **Noise Reduction:** ~80% dữ liệu social là rác (bot shill, spam). Hệ thống bắt buộc phải đi qua 2 bộ lọc: Lọc kỹ thuật (Deduplication, rate limit) và Lọc AI (Spam detection). Nếu không lọc, sentiment bị **bias dương giả** (false bullish signal).
* **Influence Weighting (PageRank / Authority):** Không phải mọi opinion đều bằng nhau. Điểm cảm xúc của một bài đăng được nhân với trọng số uy tín của người đăng (Authority Score). Một tweet từ tài khoản lớn có impact >> hàng nghìn tweet từ bot account mới tạo.
* **Divergence Logic (Galaxy Score):** Hệ thống sinh tín hiệu `BUY` khi có sự phân kỳ dương (Giá giảm/đi ngang NHƯNG Social Sentiment tăng đột biến từ các nguồn uy tín) và ngược lại.

| Tình huống | Giá | Social Sentiment | Tín hiệu |
| --- | --- | --- | --- |
| **Bullish divergence** | Giảm / sideway | Tăng mạnh từ nguồn uy tín | `BUY` — smart money accumulating |
| **Bearish divergence** | Tăng mạnh | Sentiment giảm / FUD tăng | `SELL` — distribution phase |
| **Confirmation** | Tăng + sentiment tăng | — | Trend follow |
| **Capitulation** | Giảm + sentiment giảm | — | Wait / oversold |

---

## 4. CHI TIẾT 6 BƯỚC PIPELINE

Mỗi bước dưới đây mô tả: **cơ sở lý thuyết**, **cách LunaCrush triển khai (ước lượng)**, **cách MVP triển khai cụ thể**, và **trạng thái code hiện tại** trong repo.

---

### Bước 1: Raw Collection (Thu thập đa nguồn)

**Lý thuyết:** Thu thập không chỉ nội dung post mà toàn bộ context lan truyền — likes, shares, comments, followers của author, metadata link, timestamp UTC.

**LunaCrush:** Nguồn Twitter/X (chính), Reddit, Telegram, YouTube, news sites. Ingestion qua Cloudflare Workers ở edge + backend workers. Transport Kafka. Market data qua WebSocket từ exchanges.

**MVP triển khai:**

| Thành phần | Công cụ | Vai trò |
| --- | --- | --- |
| Market OHLCV | **CCXT** + Binance WebSocket | Nến 15m/1h real-time |
| Social text | **Playwright** (scrape) hoặc **X API** (RapidAPI) | Raw events |
| Message broker | **Redpanda** topic `topic_raw_events` | JSON event async |

**Prototype hiện có:** `playground/X-API/run.py` — fetch tweet qua RapidAPI, ghi JSON local. Chưa push vào Redpanda, chưa có `event_id`/`author_id` theo contract.

**Gap cần làm:** Bọc script thành Worker daemon; thêm UUID `event_id`; producer Kafka (`confluent-kafka` hoặc `aiokafka`).

---

### Bước 2: AI Noise & Spam Filtering (Lọc nhiễu)

**Lý thuyết:** Phân biệt "Organic buzz" (người dùng thật thảo luận) và "Bot hype" (shill tự động). Hai lớp lọc:

1. **Heuristic (real-time):** dedup, rate limit per user, engagement floor
2. **ML classifier (batch):** phân loại organic vs bot

**Features quan trọng:**

* Post frequency của user (bot post liên tục)
* Engagement ratio = `(likes + RT) / followers`
* Content similarity (cosine similarity — phát hiện copy-paste)
* Account age, verified status

**MVP triển khai (ưu tiên CPU — không cần GPU):**

Thiết kế **cascade 3 tầng**: lọc rẻ trước, chỉ gọi ML khi cần. Tránh DeBERTa/FinBERT full-size ở Bước 2 (400M+ params, ~50–200ms/tweet trên CPU).

| Tầng | Công cụ | Latency ước lượng | Vai trò |
| --- | --- | --- | --- |
| **L1 — Heuristic** | Python rules + metrics Stage 1 | < 0.1ms | `--min-likes`, `--max-per-user`, engagement ratio, regex pump/spam |
| **L2 — Dedup** | **SimHash** (`simhash` lib) | < 0.5ms | Loại copy-paste / coordinated shill |
| **L3 — ML classifier** | **FastText supervised** | ~0.1–1ms/tweet | Binary `spam` / `human` (chỉ tweet chưa bị L1/L2 drop) |

**Dataset train FastText (có sẵn, không cần tự label):**

* [sandiumenge/bitcoin-tweets-spam-emotion-sentiment](https://huggingface.co/datasets/sandiumenge/bitcoin-tweets-spam-emotion-sentiment) — ~109k tweet, nhãn `spam` / `human` / `bot` (map `bot` → `spam`).

**Train FastText trên CPU (~5–15 phút):**

```bash
# Chuẩn bị file 2 cột FastText: __label__spam | __label__human <text>
pip install fasttext datasets
# fasttext supervised -input train.txt -output spam_model -dim 100 -epoch 25 -lr 0.5 -wordNgrams 2
# fasttext test spam_model.bin test.txt
```

**Quy tắc cascade (giảm ~80% lượng gọi ML):**

```text
tweet → L1 heuristic (DROP nếu rõ ràng spam/rác)
      → L2 SimHash (DROP nếu trùng nội dung gần)
      → L3 FastText (DROP nếu score spam > threshold, mặc định 0.5)
      → pass sang Bước 3 (NER)
```

**Nếu cần độ chính xác cao hơn mà vẫn CPU:** fine-tune **DistilBERT** (~66M params) + export **ONNX INT8** (`optimum[onnxruntime]`) — chậm hơn FastText ~10–20× nhưng vẫn chấp nhận được (~5–15ms/tweet). Chỉ dùng cho tweet **borderline** (FastText score 0.4–0.6), không chạy toàn bộ feed.

**Không khuyến nghị cho CPU-only:** `deberta-v3-large`, `bertweet-base` full precision ở hot path — dùng offline/batch re-label hoặc khi có GPU.

**Prototype hiện có:** X-API có quality gates (engagement floor, cap per author) — tương đương L1, chưa có SimHash/FastText.

**Gap cần làm:** Script train FastText từ dataset sandiumenge; tích hợp SimHash dedup; bọc cascade vào Worker 2 consumer Redpanda.

---

### Bước 3: Entity Recognition & Mapping (NER — gán coin)

**Lý thuyết:** Một tweet có thể mention nhiều coin: *"I love $BTC and the new updates on Ethereum"* → map sang `BTC` và `ETH`. NER trong domain crypto khác NLP thông thường vì cashtag `$SOL` ≠ từ "sol", alias đa dạng (Bitcoin = BTC = ₿), và context ("ETH killer" có thể nói về competitor).

**LunaCrush:** Custom NER model + dictionary lookup (symbol, name, contract address). Multi-label: 1 post → N coin entities.

**MVP triển khai:**

| Thành phần | Công cụ | Vai trò |
| --- | --- | --- |
| NER + keyword | **spaCy** (`en_core_web_sm` + custom EntityRuler) | Detect `$BTC`, "Ethereum", "Solana" |
| Coin registry | JSON/PostgreSQL lookup table | Map alias → `coin_id` (Top 10 MVP) |
| Regex fallback | Python `re` | Cashtag pattern `\$[A-Z]{2,10}` |

**Lưu ý:** 1 event có thể **fan-out** thành nhiều message (1 per coin) nếu mention nhiều coin.

**Gap cần làm:** Build spaCy EntityRuler với patterns cho Top 10 coins.

---

### Bước 4: Sentiment Analysis (Phân tích cảm xúc)

**Lý thuyết (Behavioral Finance):** Tâm lý đám đông (herd behavior) ảnh hưởng giá ngắn hạn. Không chỉ Pos/Neg/Neu mà cần **Sentiment Strength** — "slightly bullish" ≠ "extremely bullish".

**Thách thức domain crypto:** slang ("to the moon", "rekt", "wagmi"), sarcasm, emoji-heavy posts → model general-purpose (VADER, TextBlob) không đủ; cần **FinBERT** fine-tune trên crypto corpus.

**MVP triển khai:**

| Thành phần | Công cụ | Vai trò |
| --- | --- | --- |
| Sentiment model | **FinBERT** (`ProsusAI/finbert` qua Hugging Face) | Inference Pos/Neg/Neu |
| Serving | **FastAPI** microservice | Batch inference, GPU optional |
| Cache | **Redis** | Sentiment aggregate theo coin/timeframe |
| History | **TimescaleDB** | Lưu time-series sentiment |

**Công thức aggregate (theo giờ):**

```
weighted_sentiment = Σ(sentiment_i × influence_i) / Σ(influence_i)
```

**Prototype tương đương (external API):** `playground/alpha_vantage/filter_news_response.py` — weighted sentiment theo ticker relevance từ Alpha Vantage `NEWS_SENTIMENT`. Không phải FinBERT tự host.

**Gap cần làm:** FastAPI service load FinBERT; consume từ `topic_clean_events`.

---

### Bước 5: Influence Weighting (Trọng số ảnh hưởng)

**Lý thuyết:** Authority model — influence score kết hợp follower count (log-scale), engagement rate lịch sử, network centrality, verified/KOL status.

**Công thức đơn giản hóa (MVP):**

```
influence = log10(followers + 1) × engagement_rate × verified_bonus
engagement_rate = avg(likes + RT + replies) / followers
```

**MVP triển khai:**

| Thành phần | Công cụ | Vai trò |
| --- | --- | --- |
| Score calculator | Python Worker 3 | Tính authority từ metrics Stage 1 |
| Cache | **Redis** key `author_auth:{id}` | Lookup nhanh khi aggregate sentiment |
| Graph (optional) | **Neo4j** | Follow graph, PageRank nâng cao |

**Lý thuyết graph (Neo4j):** Account được nhiều KOL follow → authority cao hơn dù follower ít (phát hiện "hidden influencers").

**Gap cần làm:** Influence Worker; metrics từ X-API (`favorite_count`, `retweet_count`) đủ để bắt đầu công thức đơn giản.

---

### Bước 6: Proprietary Scoring (Galaxy Score & Signals)

**Lý thuyết:** Kết hợp social metrics (volume, sentiment, engagement) với market metrics (price change, volume, volatility) để sinh tín hiệu đầu tư. Galaxy Score™ của LunaCrush là metric tổng hợp 0–100 ranking coin theo "social health".

**MVP triển khai:**

| Thành phần | Công cụ | Vai trò |
| --- | --- | --- |
| Time-series model | **PyTorch Temporal Fusion Transformer (TFT)** | Dự đoán giá từ OHLCV + sentiment |
| Data prep | **Polars** | Join OHLCV + weighted sentiment theo timeframe |
| Trigger | Cron 15m/1h hoặc volatility spike | Chạy inference |
| Output | `topic_signals` + TimescaleDB | BUY/SELL + confidence |
| Orchestrator | **NestJS** | Gọi Redis sentiment + AI service → Telegram bot |

**Input (batch mỗi 1h):**

```
OHLCV (15m candles, last 96 bars)
+ weighted_sentiment (last 1h, 4h, 24h rolling)
+ influence-weighted social volume
```

**TFT lý thuyết:** Transformer cho time-series, xử lý static covariates (coin_id) + known future inputs (time of day) + observed inputs (price, sentiment history) — phù hợp multimodal prediction hơn LSTM thuần.

**Gap cần làm:** Chưa có model `.pt` và training pipeline. Bước đầu có thể dùng **rule-based divergence** (không cần TFT) để validate correlation trước khi train deep model.

---

### Trạng thái triển khai hiện tại

| Bước | LunaCrush | MVP spec | Code hiện có |
| --- | --- | --- | --- |
| 1 Raw Collection | Edge workers + Kafka | CCXT + X-API → Redpanda | `playground/X-API/run.py` (batch JSON) |
| 2 Spam Filter | Proprietary ML | FastText + heuristic | Heuristic only trong X-API |
| 3 NER | Custom NER | spaCy EntityRuler | Chưa có |
| 4 Sentiment | Crypto RoBERTa | FinBERT + FastAPI | AV news sentiment (external) |
| 5 Influence | Social graph | Redis + Neo4j | Chưa có |
| 6 Scoring | Galaxy Score™ | TFT + divergence rules | Chưa có |
| Infra | Kafka, Redis, TSDB | Redpanda, Redis, TimescaleDB, Neo4j | Chưa có docker-compose |

---

### Lộ trình triển khai đề xuất

Không cần xây hết 6 bước cùng lúc. Thứ tự hợp lý:

1. **Correlation study** — Binance OHLCV + X sentiment trung bình/giờ (script batch, như playground hiện tại)
2. **Infra minimal** — `docker compose`: Redpanda + Redis + TimescaleDB
3. **Worker 1** — bọc X-API thành producer `topic_raw_events`
4. **Worker 2+3** — heuristic filter + regex cashtag (không cần ML ngay)
5. **Worker 4** — FinBERT FastAPI service
6. **Rule-based divergence** — validate signal trước khi train TFT
7. **Worker 5 TFT** — khi đủ dữ liệu lịch sử (≥2–4 tuần)

---

## 5. LUỒNG XỬ LÝ DỮ LIỆU (TEXT FLOW DIAGRAM)

```text
[Nguồn Dữ liệu: Binance, X, Telegram]
       │
       ▼
(Worker 1: Scraper/CCXT) -- Định dạng Raw Event          ← Bước 1
       │
       ▼
[Redpanda Topic: `topic_raw_events`]
       │
       ▼
(Worker 2: FastText + spaCy) -- Lọc Spam, Khử trùng, NER  ← Bước 2 + 3
       │
       ▼
[Redpanda Topic: `topic_clean_events`]
       │
       ├──► (Worker 3: Influence Scoring) -- Redis & Neo4j  ← Bước 5
       │
       ▼
(Worker 4: FinBERT) -- Chấm điểm Sentiment (-1 đến 1)      ← Bước 4
       │
       ▼
[Redis: Tạm lưu Feature] + [TimescaleDB: Lưu lịch sử Sentiment]
       │
       ▼ (Cron 15m/1h hoặc Trigger theo Volatility)
(Worker 5: PyTorch TFT Model) -- OHLCV + Weighted Sentiment ← Bước 6
       │
       ▼
[TimescaleDB: Lưu Signal] <──► (NestJS API Gateway) ──► [Next.js Dashboard]
                                       │
                                       ▼
                              (Telegraf: Bot Service) ──► [Telegram Alerts]
```

---

## 6. THÀNH PHẦN HỆ THỐNG VÀ TRÁCH NHIỆM COMPONENT

| Component | Chủ sở hữu | Tech Stack | Trách nhiệm chính |
| --- | --- | --- | --- |
| **Infra/Broker** | CTO | Docker, Redpanda | Quản lý vòng đời Message, cấu hình Retention, cấp phát tài nguyên. |
| **Data Ingest Worker** | CTO | Python, CCXT, Playwright | Lấy nến OHLCV real-time và scrape text từ MXH. |
| **Clean & NER Worker** | Member 3 | Python, FastText, spaCy | Drop tin spam/trùng lặp. Tìm từ khóa ($BTC, Ethereum) map vào `coin_id`. |
| **Sentiment Brain** | CTO | FinBERT, Hugging Face | Chạy Inference NLP để ra chỉ số Pos/Neg/Neu. |
| **Influence Worker** | Member 4 | Python, Neo4j | Tính Authority score dựa trên followers/engagement. Cập nhật Redis. |
| **Scoring Engine** | CTO | PyTorch (TFT), Polars | Chạy Time-series prediction lấy output cuối cùng. |
| **Core API** | Member 2 | NestJS, Prisma, Socket.io | Orchestrator, CRUD Users, Push WebSocket. |
| **Frontend/Bot** | Member 1 & 4 | Next.js, Tailwind, Telegraf | Hiển thị Chart (Lightweight Charts), đẩy thông báo Tele. |

---

## 7. INPUT / OUTPUT CỦA TỪNG STAGE (DATA CONTRACTS)

### Stage 1: Raw Collection

* **Input:** Dữ liệu thô từ HTTP response / Websocket.
* **Output (Push to `topic_raw_events`):**

```json
{
  "event_id": "uuid",
  "source": "twitter",
  "raw_text": "Buy $BTC now, to the moon! \ud83d\ude80",
  "author_id": "user_123",
  "metrics": {"followers": 15000, "likes": 200},
  "timestamp": 1716110997
}
```

### Stage 2 & 3: Clean & NER Mapping

* **Input:** Lấy từ `topic_raw_events`.
* **Output (Push to `topic_clean_events`):**

```json
{
  "event_id": "uuid",
  "coin_id": "BTC",
  "clean_text": "Buy BTC now to the moon",
  "author_id": "user_123",
  "is_spam": false,
  "timestamp": 1716110997
}
```

*(Note: Nếu `is_spam: true`, drop event, không push. Nếu mention nhiều coin, fan-out thành nhiều message.)*

### Stage 4: Sentiment Analysis

* **Input:** Lấy từ `topic_clean_events`.
* **Output (Push to TimescaleDB & Redis Cache):**

```json
{
  "coin_id": "BTC",
  "sentiment_score": 0.85,
  "sentiment_label": "positive",
  "author_id": "user_123",
  "timestamp": 1716110997
}
```

### Stage 5: Influence Weighting (Background Task)

* **Input:** Metrics từ Stage 1 + Quan hệ follower (nếu có).
* **Output (Update to Redis key `author_auth:user_123`):**

```json
{
  "author_id": "user_123",
  "influence_score": 0.75,
  "updated_at": 1716110000
}
```

### Stage 6: Scoring Engine (Dự đoán)

* **Input:** Batch data từ TimescaleDB/Redis (OHLCV + Aggregated Weighted Sentiment trong 1h qua).
* **Output (Push to `topic_signals` & TimescaleDB):**

```json
{
  "signal_id": "uuid",
  "coin_id": "BTC",
  "timeframe": "1h",
  "action": "BUY",
  "confidence": 82.5,
  "target_price": 71000,
  "stop_loss": 68000,
  "timestamp": 1716111000
}
```

---

## 8. HƯỚNG DẪN TRIỂN KHAI (DEPLOYMENT & SETUP)

### 8.1. Cấu trúc Repository (Monorepo hoặc Multi-repo)

Khuyến nghị sử dụng Multi-repo cho Microservices để tách biệt CI/CD:

* `crypto-infra` (Chứa `docker-compose.yml`, config files).
* `crypto-data-workers` (S1, S2, S3, S4, S5 - Python).
* `crypto-ai-brain` (S6 - Python/PyTorch).
* `crypto-backend` (NestJS).
* `crypto-web` (Next.js).

### 8.2. Setup Local Workflow

1. Clone repo `crypto-infra`.
2. Chạy `docker compose up -d redpanda redis timescale neo4j`.
3. Cấu hình `.env` cho từng Worker trỏ về `localhost` của các DB.
4. Khởi chạy NestJS API Gateway.
5. Khởi chạy các Python Workers theo thứ tự: S1 $\rightarrow$ S2/S3 $\rightarrow$ S4.

### 8.3. Deployment Workflow (Production)

* Sử dụng **GitHub Actions**.
* Khi merge vào `main`, CI build Docker images và push lên GitHub Container Registry (GHCR).
* CD SSH vào server Ubuntu, pull image mới nhất và chạy lệnh `docker compose up -d --build`.

---

## 9. QUY TRÌNH VẬN HÀNH CƠ BẢN

* **Cold Start Sequence:**
  1. Check OS/RAM/Disk.
  2. Start Storage (TimescaleDB, Redis, Neo4j).
  3. Start Broker (Redpanda).
  4. Start API (NestJS).
  5. Start Data Workers (đảm bảo Topic đã tồn tại trước khi push).

* **Model Retraining:** Set up Cronjob hàng tuần. Lấy dữ liệu lịch sử từ TimescaleDB $\rightarrow$ Train lại file `.pt` (PyTorch) $\rightarrow$ Hot-reload AI model Worker mà không làm downtime pipeline.

---

## 10. LƯU Ý VỀ MỞ RỘNG (SCALING), MONITORING & FAULT TOLERANCE

### 10.1. Monitoring & Observability

* **Prometheus & Grafana:** Cài đặt Node Exporter (Server metrics) và custom metrics cho Python Workers (Số event xử lý/giây, độ trễ API Binance).
* **Model Drift Detection:** Cảnh báo qua Slack/Telegram nếu Tỷ lệ `confidence` của Model S6 giảm liên tục dưới 50% trong 24h.

### 10.2. Scaling Strategy

* **Worker Scaling:** Do thiết kế theo Event-driven, nếu dữ liệu thị trường biến động mạnh (Crash/Pump), số lượng tin nhắn tăng x10. Lúc này chỉ cần scale ngang (Horizontal Scale) các Container của Worker S2/S3/S4 bằng lệnh `docker compose up --scale worker_clean=3`.
* **DB Scaling:** Sử dụng TimescaleDB chunks tối ưu theo thời gian (1 ngày/chunk) để tăng tốc độ read/write cho OHLCV.

### 10.3. Fault Tolerance

* **Redpanda Retention:** Cấu hình Topic retention là 24h. Nếu AI Worker chết, dữ liệu vẫn nằm trên Queue, khi Worker sống lại sẽ tiếp tục consume không bị mất data.
* **Rate Limit/Ban IP:** Worker Scraping (S1) sử dụng mảng Rotating Proxies để tránh bị Twitter/Telegram ban IP. Lỗi API từ Binance được xử lý bằng Exponential Backoff. Khớp nối Dead-letter Queue (DLQ) cho các message bị lỗi parse JSON.
