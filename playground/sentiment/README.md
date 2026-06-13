# Stage 4 — Sentiment Analysis

Module phân tích cảm xúc (sentiment) cho hệ thống crypto social prediction pipeline.

## Mục đích

Biến dữ liệu text đã clean và đã map coin (từ Stage 2 + Stage 3) thành điểm cảm xúc dạng số:

```
mapped_events (coin_id + clean_text)
  → NLP model (FinBERT / CryptoBERT)
  → sentiment_score [-1, +1]
  → sentiment_label: positive / neutral / negative
  → sentiment_events (MongoDB)
  → aggregate theo coin_id + timeframe
```

## Pipeline Stage

```
Stage 1: Raw Collection      → raw_events
Stage 2: Spam / Noise Filter → clean_events
Stage 3: NER / Coin Mapping  → mapped_events
Stage 4: Sentiment Analysis  → sentiment_events  ← MODULE NÀY
Stage 5: Influence Weighting
Stage 6: Scoring / Prediction
```

## Input

**Collection**: `mapped_events` (ưu tiên) hoặc `clean_events` (fallback)

```json
{
  "event_id": "uuid",
  "mapped_id": "uuid",
  "parent_event_id": "uuid",
  "source": "twitter",
  "coin_id": "BTC",
  "clean_text": "Buy BTC now to the moon",
  "author_id": "user_123",
  "metrics": {
    "followers": 15000,
    "likes": 200,
    "retweets": 35,
    "replies": 12
  },
  "timestamp": 1716110997
}
```

## Output

**Collection**: `sentiment_events`

```json
{
  "sentiment_id": "uuid",
  "mapped_id": "uuid",
  "event_id": "uuid",
  "parent_event_id": "uuid",
  "coin_id": "BTC",
  "source": "twitter",
  "clean_text": "Buy BTC now to the moon",
  "author_id": "user_123",
  "metrics": { "followers": 15000, "likes": 200 },
  "timestamp": 1716110997,

  "sentiment_score": 0.85,
  "sentiment_label": "positive",
  "sentiment_confidence": 0.91,
  "probabilities": {
    "positive": 0.91,
    "neutral": 0.06,
    "negative": 0.03
  },
  "sentiment_model": "ProsusAI/finbert",
  "scored_at": "2026-06-11T00:00:00Z"
}
```

**Collection**: `sentiment_aggregates` (khi chạy `--aggregate`)

```json
{
  "coin_id": "BTC",
  "timeframe": "1h",
  "window_start": "2026-06-11T10:00:00Z",
  "window_end": "2026-06-11T11:00:00Z",
  "event_count": 245,
  "avg_sentiment": 0.37,
  "weighted_sentiment": 0.42,
  "positive_count": 160,
  "neutral_count": 50,
  "negative_count": 35,
  "updated_at": "2026-06-11T11:00:02Z"
}
```

## Cài đặt

```bash
cd playground/sentiment

# Cài dependencies
pip install -r requirements.txt

# Tạo file .env từ template
cp .env.example .env
# Sửa MONGODB_URI nếu cần
```

## Cấu hình `.env`

```env
# MongoDB (mặc định đọc từ playground/ingest/.env)
# MONGODB_URI=mongodb://localhost:27017
# MONGODB_DB=crypto_mvp

# Model (mặc định ProsusAI/finbert)
SENTIMENT_MODEL=ProsusAI/finbert
SENTIMENT_BATCH_SIZE=100
SENTIMENT_MAX_LENGTH=256
SENTIMENT_USE_RULE_FALLBACK=true
```

### Model hỗ trợ

| Model | Mô tả | Khi nào dùng |
|---|---|---|
| `ProsusAI/finbert` | FinBERT — financial sentiment | **Mặc định**, phù hợp news/financial text |
| `ElKulako/cryptobert` | CryptoBERT — crypto-specific | Twitter/Reddit crypto slang |
| `wonrax/phobert-base-vietnamese-sentiment` | PhoBERT — tiếng Việt | Nếu event là tiếng Việt |

## Cách chạy

### Batch scoring

```bash
# Score 100 events đầu tiên
python -m playground.sentiment.run --limit 100

# Score 1000 events từ Twitter
python -m playground.sentiment.run --limit 1000 --source twitter

# Dry run (không ghi MongoDB)
python -m playground.sentiment.run --limit 50 --dry-run
```

### Aggregate theo timeframe

```bash
# Aggregate 1 giờ
python -m playground.sentiment.run --aggregate --timeframe 1h

# Aggregate 15 phút, chỉ coin BTC
python -m playground.sentiment.run --aggregate-only --timeframe 15m --coin BTC

# Score + aggregate cùng lúc
python -m playground.sentiment.run --limit 500 --aggregate --timeframe 1h
```

### Chạy tests

```bash
cd playground/sentiment
python tests/test_scorer.py
```

## Output mong muốn khi chạy

```
[INFO] Connected to MongoDB: crypto_mvp
[INFO] Input collection: mapped_events (245 events)
[INFO] Output collection: sentiment_events
[INFO] Loading sentiment model: ProsusAI/finbert
Processing: 100%|██████████████████| 245/245
[INFO] processed=232 skipped=10 errors=3 inserted=232
```

## Giải thích sentiment_score

```
Score     Label       Ý nghĩa
─────     ─────       ───────
+0.8..+1  positive    Rất tích cực (bullish, moon, pump)
+0.15..+0.8 positive  Tích cực
-0.15..+0.15 neutral  Trung tính
-0.8..-0.15 negative  Tiêu cực
-1..-0.8  negative    Rất tiêu cực (crash, rekt, scam)
```

### Cách tính

**Ưu tiên 1**: Alpha Vantage score có sẵn (nếu event có `extra.ticker_sentiment`)

**Ưu tiên 2**: NLP model (FinBERT/CryptoBERT)
```python
sentiment_score = positive_probability - negative_probability  # [-1, +1]
```

**Ưu tiên 3**: Rule-based fallback (crypto slang: moon, rekt, bullish, bearish...)

### Weighted aggregate

```python
influence = 1 + log1p(followers) + 0.1 * likes + 0.3 * retweets + 0.2 * replies
weighted_sentiment = Σ(score_i × influence_i) / Σ(influence_i)
```

## Cấu trúc module

```
playground/sentiment/
├── README.md            ← Hướng dẫn này
├── run.py               ← CLI worker chính
├── requirements.txt     ← Dependencies
├── .env.example         ← Template config
├── lib/
│   ├── __init__.py
│   ├── config.py        ← Đọc .env config
│   ├── mongo.py         ← MongoDB CRUD + indexes
│   ├── scorer.py        ← HuggingFace NLP scorer + AV fallback
│   ├── rule_based.py    ← Fallback rule-based crypto slang
│   ├── schema.py        ← Document builder
│   ├── aggregate.py     ← Aggregate coin + timeframe
│   └── utils.py         ← Logging setup
└── tests/
    ├── __init__.py
    └── test_scorer.py   ← Unit tests
```

## Chống duplicate

Module sử dụng unique index trên MongoDB để chạy lại nhiều lần không bị insert trùng:

```python
# Index 1: mapped_id + coin_id (unique, sparse)
# Index 2: event_id + coin_id (unique, sparse)
```

Mỗi event được check `already_scored()` trước khi gọi model. Nếu đã có → skip.

## Hướng mở rộng

### Phase 2: FastAPI Sentiment Service

```
playground/sentiment_api/
├── main.py              ← FastAPI app
├── model.py             ← Shared scorer
└── requirements.txt
```

Endpoint:
```http
POST /score
Content-Type: application/json

{"text": "BTC to the moon", "source": "twitter", "coin_id": "BTC"}
```

### Phase 3: Streaming

- **Redpanda/Kafka consumer**: Đọc topic `mapped_events`, ghi topic `sentiment_events`
- **Redis cache**: Cache score cho text trùng lặp
- **TimescaleDB**: Thay MongoDB cho time-series aggregate

### Phase 4: Multi-model

- Ensemble nhiều model (FinBERT + CryptoBERT + rule-based)
- Fine-tune model trên crypto-specific dataset
- Language detection tự động → chọn model phù hợp
