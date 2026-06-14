# Slide báo cáo BTL — Hệ quản trị CSDL

> **Đề tài:** Xây dựng hệ thống khai thác và dự đoán thị trường crypto từ sàn giao dịch Binance và đưa ra gợi ý đầu tư  
> **Nhóm 5** · GVHD: Trần Quốc Khánh · Học viện Công nghệ Bưu chính Viễn thông  
> **Thời lượng gợi ý:** 15–20 phút (~25 slide)  
> **Cách dùng:** Mỗi slide cách nhau bởi `---`. Có thể import vào PowerPoint, Google Slides hoặc [Marp](https://marp.app/).

---

## Slide 1 — Trang bìa

**BÁO CÁO BÀI TẬP LỚN**

**Hệ quản trị cơ sở dữ liệu**

**Đề tài:** Xây dựng hệ thống khai thác và dự đoán thị trường crypto từ sàn giao dịch Binance và đưa ra gợi ý đầu tư

**Crypto Social Intelligence Pipeline**

- Giảng viên hướng dẫn: **Trần Quốc Khánh**
- Nhóm thực hiện: **Nhóm 5**
- Ngày báo cáo: …

*Ảnh gợi ý:* `media/image102.png`

**Ghi chú trình bày:** Giới thiệu ngắn tên đề tài và nhóm (30 giây).

---

## Slide 2 — Thành viên & phân công

| STT | Họ và tên | MSSV | Module phụ trách |
|-----|-----------|------|-----------------|
| 1 | Bùi An Du | B23DCKH026 | Kiến trúc, CSDL, Ingest, tích hợp, báo cáo |
| 2 | Thiều Quang Mạnh | B23DCKH075 | Influence Weighting |
| 3 | Đinh Việt Dũng | B23DCKH031 | Sentiment Score |
| 4 | Nguyễn Vĩnh Tùng | B23DCKH130 | Influence (Kafka/Redis worker) |
| 5 | Ngô Văn Phương | B23DCKH092 | Proprietary Scoring |

**Ghi chú trình bày:** Mỗi thành viên tự giới thiệu phần mình (1 phút/người khi hỏi chi tiết).

---

## Slide 3 — Mục lục

1. Vấn đề & mục tiêu
2. Tổng quan hệ thống
3. Pipeline 7 giai đoạn xử lý dữ liệu
4. **Thiết kế cơ sở dữ liệu MongoDB** *(trọng tâm môn học)*
5. Kiến trúc & giao diện web
6. Hiện thực, kiểm thử & đánh giá
7. Kết luận & hướng phát triển

---

## Slide 4 — Bối cảnh & vấn đề

**Thị trường crypto phản ứng nhanh trước:**
- Tin tức, phát biểu KOL, tâm lý cộng đồng trên mạng xã hội
- Dư luận social có thể **thay đổi trước** khi giá biểu hiện rõ trên chart

**Thách thức khi khai thác dữ liệu social:**
- Đa nguồn, đa định dạng (Twitter/X, Reddit, tin tài chính…)
- Nhiễu: spam, bot, shill, copy-paste campaign
- Một bài viết có thể đề cập **nhiều coin** (cashtag, slang)
- Không chuẩn hóa → sentiment tổng hợp **sai lệch**

**Giải pháp:** Pipeline modular 7 stage + MongoDB làm event store trung tâm

---

## Slide 5 — Mục tiêu đề tài

**Mục tiêu tổng quát:** Biến dữ liệu social/news thành đặc trưng định lượng → hỗ trợ đánh giá xu hướng ngắn hạn coin phổ biến.

| # | Mục tiêu cụ thể | Kết quả |
|---|-----------------|---------|
| 1 | Thu thập đa nguồn, schema thống nhất | `raw_events` với event_id, metrics, timestamp |
| 2 | Giảm dữ liệu rác | Cascade L1→L2→L3; PASS/DROP |
| 3 | Map coin trong bài viết | Top 10 coin; fan-out 1 post → N events |
| 4 | Sentiment & aggregate | Score ∈ [-1, 1]; cửa sổ 15m–1d |
| 5 | Influence + tín hiệu | Weighted sentiment; BUY/HOLD/SELL |

**Ranh giới:** Không giao dịch tự động · Không cam kết lợi nhuận · Không thay tư vấn tài chính

---

## Slide 6 — Phạm vi & công nghệ

**Phạm vi dữ liệu**
- Ngôn ngữ: **tiếng Anh**
- Nguồn: Twitter/X (RapidAPI), Alpha Vantage, Yahoo Finance, Reddit
- Coin: **BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, LINK**
- Timeframe: 15m, 30m, 1h, 4h, 1d (scoring mặc định **1h**)

**Stack chính**
- **MongoDB 7** — event store, sessions, jobs
- **Python 3.12** — pipeline workers
- **FastAPI + WebSocket** — API & realtime
- **React 19** — Dashboard, Chat, ETL Monitor
- **FinBERT, FastText, Polars, CCXT, OpenRouter**

---

## Slide 7 — Tổng quan sản phẩm

**Crypto Social Intelligence Pipeline** — ứng dụng web full-stack

```
Dashboard TradingView → nút "Phân tích" → Chat (planning + ETL progress + LLM report) → Tải PDF
```

**Luồng người dùng**
1. Xem chart nến + giá realtime (Binance/CCXT)
2. Chọn coin & timeframe → bấm **Phân tích**
3. Theo dõi 7 stage qua WebSocket
4. Nhận báo cáo LLM + tín hiệu BUY/HOLD
5. Lưu session, xem lại lịch sử, export PDF

*Ảnh gợi ý:* `media/image113.png` (luồng dữ liệu tổng quan)

---

## Slide 8 — Pipeline 7 giai đoạn (tổng quan)

| Stage | Tên | Input → Output MongoDB |
|-------|-----|------------------------|
| **1** | Ingest | API → `raw_events` |
| **2** | Filter | `raw_events` → `clean_events` / `dropped_events` |
| **3** | NER & Mapping | `clean_events` → `mapped_events` (fan-out) |
| **4** | Sentiment | `mapped_events` → `sentiment_events` |
| **5** | Influence | `sentiment_events` → `influence_aggregates` |
| **6** | Scoring | aggregates + OHLCV → `scoring_signals` |
| **7** | LLM Insight | signals + context → `analysis_reports` |

**Nguyên tắc:** Mỗi stage = một data contract · Idempotent · Fail fast

*Ảnh gợi ý:* `media/image96.png` (kiến trúc tầng)

---

## Slide 9 — Stage 1: Thu thập & chuẩn hóa (Ingest)

**Vai trò:** Nhiều API → **một schema raw event** thống nhất

**Thành phần:** Collector → Adapter → Validator → Dedup → Persistence

**Schema chính (`raw_events`)**
- `event_id`, `source`, `external_id`
- `raw_text`, `author_id`, `metrics`
- `timestamp` (event time), `ingested_at` (processing time)

**Chống trùng:** Unique index `(source, external_id)` — chạy lại an toàn

*Ảnh gợi ý:* `media/image101.png`, `media/image93.png`

**Người trình bày:** Bùi An Du

---

## Slide 10 — Stage 2: Lọc spam & nhiễu

**Cascade 3 tầng — lọc rẻ trước, model nặng sau**

| Tầng | Công nghệ | Latency | Chức năng |
|------|-----------|---------|-----------|
| **L1** | Heuristic | ~0.1 ms | Regex pump, engagement ratio, cap/author |
| **L2** | SimHash | ~0.5 ms | Near-duplicate, coordinated copy-paste |
| **L3** | FastText | ~1 ms | Binary spam/human classifier |

**Output:** PASS → `clean_events` · DROP → `dropped_events` (audit)

*Ảnh gợi ý:* `media/image103.png`, `media/image98.png`

---

## Slide 11 — Stage 3: NER & ánh xạ coin

**Bài toán:** Xác định coin nào được đề cập trong mỗi bài viết

- Registry **Top 10 coin** (`config/coin_registry.json`)
- Rules: cashtag `$BTC`, tên viết tắt, keyword
- **Hybrid mode:** Rules trước → LLM (OpenRouter) khi cần
- **Fan-out:** 1 post → N bản ghi `mapped_events` (1 row / coin)

**Collection:** `mapped_events` — unique `(parent_event_id, coin_id)`

*Ảnh gợi ý:* `media/image115.png`, `media/image117.png`

---

## Slide 12 — Stage 4: Sentiment Score

**Mô hình:** FinBERT (Transformer cho ngôn ngữ tài chính)

**Công thức:** \( S = P_{pos} - P_{neg} \), \( S \in [-1, 1] \)

| Khoảng S | Nhãn |
|----------|------|
| S ≥ 0.15 | Positive |
| -0.15 < S < 0.15 | Neutral |
| S ≤ -0.15 | Negative |

**Fallback:** Alpha Vantage score sẵn → FinBERT → rule-based keywords

**Aggregate:** Theo `(coin_id, timeframe)` — avg & weighted

*Ảnh gợi ý:* `media/image66.png`

**Người trình bày:** Đinh Việt Dũng

---

## Slide 13 — Stage 5: Influence Weighting

**Vì sao cần trọng số?** Không phải mọi bài viết có giá trị ngang nhau.

**Công thức heuristic (MVP):**
```
influence_weight = SourceWeight × TimeDecay × QualityScore
                 × AuthorAuthority × EngagementStrength × ViralitySurprise

weighted_sentiment = sentiment_score × influence_weight
```

**Aggregate cửa sổ** → `influence_aggregates` — **input chuẩn cho Stage 6**

**Transport (scale-out):** Kafka/Redpanda + Redis Streams

**Người trình bày:** Thiều Quang Mạnh & Nguyễn Vĩnh Tùng

---

## Slide 14 — Stage 6: Scoring & phát hiện phân kỳ

**Join:** `influence_aggregates` + OHLCV Binance (CCXT/Polars)

**Dual-score:**
- **Galaxy Alpha Score** — cơ hội (sentiment + volume social)
- **Safety Score** — rủi ro (volatility, CARA penalty)

**Quy tắc đầu ra:** BUY / HOLD / SELL → `scoring_signals`

**Phát hiện phân kỳ:** So sánh sentiment vs giá (KL divergence — metadata)

*Ảnh gợi ý:* `media/image71.png`

**Người trình bày:** Ngô Văn Phương

---

## Slide 15 — Stage 7: LLM Insight & báo cáo

**Sau scoring:** OpenRouter đọc signal + sentiment + influence + giá

**Output:**
- `analysis_reports` — tóm tắt, rủi ro, divergence, khuyến nghị
- `chat_messages` — stream vào UI chat
- Export **PDF** (WeasyPrint)

**Lưu ý:** Stage 7 **chỉ diễn giải** — không thay đổi action rule của Stage 6

*Ảnh gợi ý:* `media/image75.png`, `media/image106.png`

---

## Slide 16 — Thiết kế CSDL MongoDB *(trọng tâm)*

**Database:** `crypto_mvp` · Connection qua `MONGODB_URI`

**Mô hình:** Document-oriented — mỗi stage ghi collection riêng, join qua `coin_id` + `timestamp`

*Ảnh gợi ý:* `media/image109.png` (ERD)

**Lý do chọn MongoDB:**
- Schema linh hoạt cho metadata NLP/filter
- Fan-out N coin/post tự nhiên
- Upsert aggregate theo cửa sổ thời gian
- Phù hợp event store append-only

---

## Slide 17 — Collections chính

| Collection | Stage | Mục đích |
|------------|-------|----------|
| `raw_events` | 1 | Dữ liệu gốc bất biến |
| `clean_events` / `dropped_events` | 2 | PASS / audit DROP |
| `mapped_events` | 3 | 1 row / coin / post |
| `sentiment_events` | 4 | Score & label per event |
| `influence_aggregates` | 5 | **Input chuẩn Stage 6** |
| `scoring_signals` | 6 | BUY/HOLD/SELL |
| `analysis_reports` | 7 | Báo cáo LLM |
| `analysis_sessions`, `chat_messages` | Web | Phiên phân tích |
| `pipeline_jobs`, `pipeline_stage_runs` | Orchestrator | Audit ETL |

---

## Slide 18 — Data contract & Index

**Data contract giữa các stage (trích yếu):**
```
Stage 1→2: event_id, source, raw_text, metrics, timestamp
Stage 2→3: + clean_text, filter metadata
Stage 3→4: + coin_id, ner metadata
Stage 4→5: + sentiment_score, sentiment_label
Stage 5→6: aggregate (coin_id, timeframe, window_start, sentiment_score, social_volume)
Stage 6:   + OHLCV (close, volume)
```

**Index quan trọng (idempotent):**
- `raw_events`: unique sparse `(source, external_id)`
- `mapped_events`: unique `(parent_event_id, coin_id)`
- `influence_aggregates`: unique `(coin_id, timeframe, window_start)`
- `scoring_signals`: unique `signal_id`

---

## Slide 19 — Kiến trúc hệ thống

| Tầng | Thành phần | Trách nhiệm |
|------|------------|-------------|
| **Presentation** | React 19 + Mantine + Tailwind | Chart, Chat, ETL Monitor |
| **API + Orchestrator** | FastAPI REST + WS | Session, stream LLM/ETL |
| **Processing** | 7 Python workers | ETL social → scoring → insight |
| **Infrastructure** | MongoDB, CCXT, OpenRouter | Event store, market data, LLM |

**Nguyên tắc thiết kế module:**
1. Một stage — một contract
2. Idempotent batch
3. Fail fast
4. Separation of concerns
5. Web-first UX

*Ảnh gợi ý:* `media/image96.png`, `media/image116.png` (Use Case)

---

## Slide 20 — Giao diện web

| Màn hình | Route | Chức năng |
|----------|-------|-----------|
| Trading Dashboard | `/dashboard` | Chart TradingView, chọn coin, nút Phân tích |
| Chat phân tích | `/analysis/:id` | Planning → ETL cards → Signal → LLM stream → PDF |
| ETL Monitor | `/etl` | Graph 7 stage, progress realtime |

**API chính:**
- `GET /api/v1/market/ohlcv` — datafeed chart
- `POST /api/v1/analysis/sessions` — trigger pipeline
- `WS /ws/pipeline` — ETL progress
- `GET .../export/pdf` — tải báo cáo

*Ảnh gợi ý:* screenshot demo nếu có

---

## Slide 21 — Hiện thực & môi trường

**Hiện trạng repo:**
- Logic nghiệp vụ Stage 1–6: **`playground/`** (đã chạy thử)
- Sản phẩm đích: **`src/` + `web/`** (đang gom monorepo)

**Môi trường dev:**
- CPU 8+ cores · RAM 16 GB · Python 3.12 · Docker Compose
- FinBERT CPU OK (~500 MB model cache)

**Chạy thử module:** CLI từng stage → MongoDB local

*Ảnh gợi ý:* `media/image72.png`, `media/image81.png`

---

## Slide 22 — Kiểm thử

| Loại test | Kết quả |
|-----------|---------|
| Unit test sentiment (rule-based) | **5/5 PASS** |
| Unit test influence | **3/3 PASS** |
| Scoring mock scenarios | **3/3 PASS** |
| Integration Stage 1→6 | **PASS** (manual, batch nhỏ) |
| E2E Web + Stage 7 | Chưa đo (phụ thuộc tích hợp) |

**Kịch bản tiêu biểu:**
- TC-01: Tweet shill → DROP tại L1
- TC-03: `$BTC` → coin_id = BTC
- TC-07: Bullish divergence mock → BUY
- TC-09: Ingest 2 lần → không duplicate

---

## Slide 23 — Đánh giá hệ thống

**Ưu điểm**
- Pipeline modular 7 stage, contract MongoDB rõ ràng
- NLP phù hợp domain (FinBERT, FastText spam)
- Scoring minh bạch (Galaxy dual-score + rule)
- Observable: jobs, stage_runs, WebSocket realtime

**Hạn chế**
- Single-node; chưa scale horizontal
- Phụ thuộc API bên thứ ba (rate limit)
- Chưa backtest dài hạn (PnL)
- Sentiment chủ yếu tiếng Anh

---

## Slide 24 — Mức độ hoàn thành

| Nhóm mục tiêu | Đánh giá |
|---------------|----------|
| Thu thập & làm sạch dữ liệu | **~90–95%** |
| Phân tích nội dung & sinh tín hiệu | **~85–95%** |
| Điều phối & giao tiếp hệ thống | **~75%** |
| Giao diện & trải nghiệm người dùng | **~65–70%** |
| Báo cáo phân tích tự động (LLM) | **~70%** |

**Kết luận:** Mục tiêu cốt lõi **xử lý dữ liệu → tín hiệu** đã đạt. Sản phẩm web hoàn chỉnh cần bước tích hợp cuối.

---

## Slide 25 — Hướng phát triển

| Ưu tiên | Hướng |
|---------|-------|
| **Rất cao** | Hoàn thiện web E2E · Báo cáo LLM tự động |
| **Cao** | Orchestrator tập trung · Backtest tín hiệu · Cache OHLCV |
| **Trung bình** | Mở rộng nguồn (Telegram, RSS) · Alert · Rule SELL nâng cao |
| **Thấp** | Đa ngôn ngữ (VN) · Đa người dùng |

---

## Slide 26 — Kết luận

**Crypto Social Intelligence Pipeline** biến thông tin social ồ ạt thành gợi ý hành động có cơ sở:

- ✅ Thu thập → lọc nhiễu → map coin → sentiment → influence → scoring
- ✅ Thiết kế **MongoDB event store** với contract & index idempotent
- ✅ Thiết kế web app: chart + chat + PDF
- 🔄 Đang tích hợp: orchestrator + frontend E2E

**Không thay thế tư vấn tài chính · Không giao dịch tự động**

---

## Slide 27 — Q&A

**Cảm ơn thầy/cô và các bạn đã lắng nghe!**

**Nhóm 5 — Hệ quản trị CSDL**

*Chuẩn bị sẵn:* demo CLI pipeline · ERD MongoDB · 1 mock scoring scenario

---

# Phụ lục — Gợi ý phân công trình bày

| Phần | Slide | Người trình bày | Thời gian |
|------|-------|-----------------|-----------|
| Mở đầu & mục tiêu | 1–6 | Bùi An Du | ~3 phút |
| Pipeline Stage 1–2 | 8–10 | Bùi An Du | ~2 phút |
| Sentiment | 12 | Đinh Việt Dũng | ~2 phút |
| Influence | 13 | Thiều Quang Mạnh / Nguyễn Vĩnh Tùng | ~2 phút |
| Scoring | 14 | Ngô Văn Phương | ~2 phút |
| **CSDL MongoDB** | 16–18 | Bùi An Du | ~3 phút |
| Demo & kiểm thử | 20–22 | Cả nhóm / rotate | ~3 phút |
| Kết luận & Q&A | 23–27 | Bùi An Du | ~3 phút |

---

# Phụ lục — Checklist trước khi báo cáo

- [ ] Copy ảnh từ `docs/bao_cao/media/` vào slide (đường dẫn tương đối)
- [ ] Chuẩn bị demo: chạy 1 stage ingest hoặc scoring mock
- [ ] In/mở sẵn ERD `media/image109.png`
- [ ] Thống nhất ai trả lời câu hỏi về MongoDB index & idempotent
- [ ] Nhắc ranh giới: không phải lời khuyên đầu tư
