# Filter — Stage 2 (Spam / Noise Filtering)

Playground triển khai **Bước 2** trong pipeline crypto MVP: đọc raw social events từ MongoDB (`playground/ingest`), lọc nhiễu qua cascade **L1 heuristic → L2 SimHash → L3 FastText**, ghi kết quả sạch vào `clean_events`.

**Tham chiếu:** [`docs/pipeline-overview.md`](../../docs/pipeline-overview.md) § Bước 2 · [`docs/lunacrush-data-flow.md`](../../docs/lunacrush-data-flow.md) § Bước 2 · [`playground/ingest/README.md`](../ingest/README.md) (Stage 1)

---

## 1. Vai trò trong pipeline

```text
[ Twitter / Reddit / News … ]     ← playground/ingest (Stage 1)
              │
              ▼
        raw_events (MongoDB)
              │
              ▼
   playground/filter (Stage 2)    ← tài liệu này
              │
              ├── PASS → clean_events → Stage 3 NER
              └── DROP → (tuỳ chọn) dropped_events
```

Stage 2 **không** gán coin, **không** chấm sentiment — chỉ quyết định event có đủ tin cậy để đi tiếp hay bị loại. Output là text đã chuẩn hóa (`clean_text`) kèm metadata lọc (`filter`).

---

## 2. Cơ sở lý thuyết

### 2.1. Vì sao phải lọc trước sentiment?

Dữ liệu social crypto có tỷ lệ nhiễu rất cao. Industry ước lượng **~80%** post trên feed công khai là spam, bot shill, hoặc coordinated hype — không phản ánh ý kiến thật của cộng đồng.

Nếu bỏ qua bước lọc:

- Sentiment aggregate bị **bias dương giả** (false bullish): bot spam "to the moon", airdrop, pump group làm tăng điểm cảm xúc ảo.
- Social volume và velocity (Speed Layer) phản ánh chiến dịch marketing, không phải organic buzz.
- Tín hiệu divergence ở Stage 6 (Galaxy Score / BUY-SELL) trở nên không đáng tin.

**Mục tiêu Stage 2:** giữ **organic buzz** (người dùng thật thảo luận) và loại **bot hype** (shill tự động, copy-paste campaign).

### 2.2. Organic buzz vs Bot hype

| Đặc điểm | Organic buzz | Bot hype / shill |
| --- | --- | --- |
| Nội dung | Đa dạng, có ngữ cảnh | Copy-paste, công thức pump ("100x", "join Telegram") |
| Author | Phân bố đều nhiều account | Một account post liên tục hoặc hàng loạt account cùng nội dung |
| Engagement | Tương quan hợp lý với follower | Ratio bất thường (quá thấp hoặc quá cao so với follower) |
| Mục đích | Thảo luận, tin tức, quan điểm | Kêu gọi mua, airdrop, referral |

Playground này không phân loại cảm xúc — chỉ phân loại **có nên đưa post vào pipeline hay không**.

### 2.3. Lambda Architecture — hai tầng lọc

Theo mô hình LunarCrush (Hybrid Lambda):

| Tầng | Độ trễ | Vai trò lọc |
| --- | --- | --- |
| **Speed Layer** | Giây → phút | Heuristic real-time: dedup, rate limit, engagement floor — đủ nhanh cho dashboard |
| **Batch Layer** | 15 phút → ngày | ML nặng hơn trên cùng retention — tính lại metric dài hạn |

Playground MVP gộp cả hai vào **một batch job** đọc MongoDB (thay vì Kafka consumer), nhưng **logic cascade** giữ nguyên: lọc rẻ trước, ML sau, giảm ~80% lượng gọi model.

```text
raw event ──► [L1 heuristic] ──► [L2 SimHash] ──► [L3 FastText] ──► clean event | ∅
                  ~0.1 ms           ~0.5 ms          ~0.1–1 ms
```

### 2.4. Feature engineering

Các feature mà pipeline (và code) sử dụng, bám theo tài liệu gốc:

| Feature | Công thức / cách đo | Ý nghĩa |
| --- | --- | --- |
| **Post frequency / author cap** | Đếm event/author trong batch | Bot hoặc promoter post liên tục |
| **Engagement ratio** | `(likes + retweets + comments) / followers` | Shill account nhỏ nhưng engagement bất thường cao; hoặc account lớn nhưng engagement quá thấp |
| **Content similarity** | SimHash + Hamming distance | Phát hiện copy-paste / coordinated campaign |
| **Lexical patterns** | Regex pump/spam | "100x", "free airdrop", `t.me/`, "IDO on" — tín hiệu mạnh, latency cực thấp |
| **Text embedding (ML)** | FastText supervised | Học pattern spam tinh vi hơn rule, vẫn chạy CPU |

News (`source: news`) mặc định **bypass** L1/L3 nặng — nguồn tin đã qua biên tập, chỉ kiểm tra text rỗng. Bật `--filter-news` nếu muốn áp dụng đầy đủ.

### 2.5. Thiết kế cascade 3 tầng

**Nguyên tắc:** mỗi tầng loại một lớp nhiễu; event chỉ tới ML khi qua L1 và L2.

#### L1 — Heuristic (rule-based)

- Latency ~0.1 ms/event, không cần GPU.
- Loại rác rõ ràng: text rỗng, likes dưới ngưỡng, regex pump, cap số post/author, engagement ratio ngoài vùng hợp lý.
- Tương đương quality gates trong `playground/X-API` (min likes, max per author).

#### L2 — SimHash (near-duplicate)

- **SimHash** băm nội dung thành fingerprint 64-bit; so sánh Hamming distance ≤ 3 → coi là trùng gần.
- Phát hiện **coordinated shill**: nhiều account post cùng một đoạn text (hoặc biến thể nhỏ).
- Latency ~0.5 ms/event; index trong memory cho từng batch run.

#### L3 — FastText (supervised ML)

- Binary classifier `spam` / `human`, train trên dataset [sandiumenge/bitcoin-tweets-spam-emotion-sentiment](https://huggingface.co/datasets/sandiumenge/bitcoin-tweets-spam-emotion-sentiment) (~109k tweet).
- Train tại [`playground/finetune/fasttext`](../finetune/fasttext/README.md) → `models/spam_model.bin`.
- Latency ~0.1–1 ms/tweet trên CPU — nhanh hơn DeBERTa/FinBERT **10–100×**, phù hợp hot path.
- Ngưỡng mặc định: DROP nếu `P(spam) ≥ 0.5`. Tắt bằng `--no-ml` hoặc khi chưa có model.

**Vì sao không dùng FinBERT/DeBERTa ở Stage 2?** Model 400M+ params (~50–200 ms/tweet CPU) dành cho **sentiment** (Stage 4), không phải spam gate. Cascade FastText + heuristic đủ cho MVP; DistilBERT ONNX có thể bổ sung sau cho vùng borderline (score 0.4–0.6).

### 2.6. Kết quả mong đợi

Trên batch thử **113 events** thực từ MongoDB (dry-run):

| | Số | % |
| --- | --- | --- |
| PASS | 74 | 65.5% |
| DROP | 39 | 34.5% |

Phân bố DROP: L1 `empty_text` (10), L1 `pump_regex` (1), L3 FastText spam (28). SimHash chưa bắt duplicate trong batch này — bình thường nếu nội dung đa dạng.

Tỷ lệ DROP ~30–40% phù hợp mục tiêu giảm noise trước sentiment; tune bằng `--min-likes`, `--max-per-author`, ngưỡng FastText khi cần.

---

## 3. Kiến trúc code

```text
playground/filter/
├── run.py                 # CLI: run | stats
├── .env                   # override MongoDB / model path (gitignored)
├── .env.example
└── lib/
    ├── config.py          # load ingest/.env + filter/.env
    ├── mongo.py           # đọc raw, ghi clean/dropped
    ├── heuristic.py       # L1
    ├── dedup.py           # L2 SimHashIndex
    ├── ml.py              # L3 FastText
    ├── cascade.py         # orchestrate + FilterStats
    ├── export.py          # xuất DROP → Excel
    └── progress.py
```

**Luồng xử lý:**

1. `fetch_unprocessed_raw` — lấy event trong `raw_events` chưa có `event_id` trong `clean_events`.
2. `run_cascade` — L1 → L2 → L3 tuần tự từng event.
3. `build_clean_doc` / `build_dropped_doc` — map sang schema output.
4. Ghi MongoDB (trừ `--dry-run`).

Idempotent: unique index trên `event_id` — chạy lại chỉ xử lý event mới từ ingest.

---

## 4. Setup

```bash
# Stage 1 — phải có raw_events trước
cd playground/ingest
cp .env.example .env    # MONGODB_URI + API keys
uv sync
uv run python run.py twitter

# (Tuỳ chọn) Train FastText L3
cd ../finetune/fasttext
uv sync --group dev
uv run jupyter notebook notebooks/train_and_test.ipynb
# → models/spam_model.bin

# Stage 2
cd ../filter
cp .env.example .env    # hoặc dùng chung MONGODB_* từ ingest/.env
uv sync
```

---

## 5. Chạy

```bash
cd playground/filter

# Thống kê collection
uv run python run.py stats

# Dry-run — xem PASS/DROP, không ghi DB
uv run python run.py --dry-run -v --limit 113

# Xuất báo cáo đánh giá đầy đủ (summary + all + passed + dropped)
uv run python run.py --dry-run --export-sheet
uv run python run.py --export-sheet exports/filter_report.xlsx

# Lọc thật → clean_events
uv run python run.py --limit 113

# Chỉ twitter; lưu DROP để phân tích
uv run python run.py --source twitter --save-dropped

# Heuristic chặt hơn
uv run python run.py --min-likes 10 --max-per-author 5

# Tắt ML (chỉ L1 + L2)
uv run python run.py --no-ml
```

### CLI tham số chính

| Flag | Mặc định | Mô tả |
| --- | --- | --- |
| `--limit` | 1000 | Số event tối đa mỗi lần chạy |
| `--dry-run` | — | In stats, không ghi MongoDB |
| `--save-dropped` | — | Ghi DROP vào `dropped_events` |
| `--export-sheet` | `exports/filter_report_<ts>.xlsx` | Báo cáo Excel: summary, all, passed, dropped |
| `--no-ml` | — | Bỏ L3 FastText |
| `--min-likes` | 0 | Ngưỡng likes tối thiểu (L1) |
| `--max-per-author` | 0 | Cap event/author trong batch (0 = tắt) |
| `--min-engagement-ratio` | 0 | Ratio tối thiểu (0 = tắt) |
| `--max-engagement-ratio` | 0 | Ratio tối đa — phát hiện shill (0 = tắt) |
| `--filter-news` | — | Áp dụng L1/L3 cho `source: news` |
| `--source` | all | `twitter` \| `reddit` \| `news` |

### Export Excel — `--export-sheet`

Workbook gồm **4 sheet**:

| Sheet | Nội dung |
| --- | --- |
| `summary` | Tổng PASS/DROP, phân bố L1/L2/L3, chi tiết lý do DROP, tham số chạy |
| `all` | Toàn bộ events đã đánh giá |
| `passed` | Events qua cascade |
| `dropped` | Events bị loại |

Cột chung: Result, Filter stage/reason, event metadata, metrics, FastText score, clean/raw text. Hoạt động cả với `--dry-run`. File lưu trong `exports/` (gitignored).

---

## 6. Schema output

### Input — `raw_events` (từ ingest)

Xem [`playground/ingest/README.md`](../ingest/README.md). Trường quan trọng cho filter: `event_id`, `source`, `raw_text`, `author_id`, `metrics`, `timestamp`.

### Output PASS — `clean_events`

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "twitter",
  "raw_text": "Buy $BTC now...",
  "clean_text": "Buy $BTC now...",
  "author_id": "BitcoinMagazine",
  "metrics": { "likes": 749, "retweets": 113, "followers": 3200000 },
  "timestamp": 1714248653,
  "is_spam": false,
  "filter": {
    "stage": "PASS",
    "layers": ["heuristic", "simhash", "fasttext"],
    "fasttext": { "label": "human", "score": 0.12, "skipped": false }
  },
  "filtered_at": 1716112000
}
```

### Output DROP — `dropped_events` (cần `--save-dropped`)

```json
{
  "event_id": "...",
  "source": "twitter",
  "drop_stage": "L3",
  "drop_reason": "fasttext_spam",
  "raw_text": "Join our Telegram for 100x gains!",
  "filter": { "label": "spam", "score": 0.98 },
  "dropped_at": 1716112000
}
```

---

## 7. Biến môi trường

| Biến | Nguồn | Mô tả |
| --- | --- | --- |
| `MONGODB_URI` | `ingest/.env` hoặc `filter/.env` | Connection string Atlas |
| `MONGODB_DB` | — | Mặc định `crypto_mvp` |
| `MONGODB_COLLECTION` | — | Input: `raw_events` |
| `MONGODB_CLEAN_COLLECTION` | `filter/.env` | Output PASS: `clean_events` |
| `MONGODB_DROPPED_COLLECTION` | `filter/.env` | Output DROP: `dropped_events` |
| `FASTTEXT_MODEL_PATH` | `filter/.env` | Mặc định `../finetune/fasttext/models/spam_model.bin` |

`lib/config.py` load **`playground/ingest/.env` trước**, sau đó **`playground/filter/.env`** (override nếu trùng key).

---

## 8. Bước tiếp theo

| Bước | Playground | Input |
| --- | --- | --- |
| Stage 3 — NER & coin mapping | *(chưa có)* | `clean_events` |
| Stage 4 — Sentiment | FinBERT / CryptoBERT | event đã gán `coin_id` |
| Production | Worker + Kafka | `topic_raw_events` → `topic_clean_events` |

---

## 9. Tài liệu liên quan

- [Pipeline MVP — Bước 2](../../docs/pipeline-overview.md) — cascade spec, dataset FastText, so sánh model
- [LunarCrush data flow — Bước 2](../../docs/lunacrush-data-flow.md) — organic vs bot, feature gốc
- [FastText train](../finetune/fasttext/README.md) — huấn luyện model L3
- [Ingest Stage 1](../ingest/README.md) — thu thập raw events
