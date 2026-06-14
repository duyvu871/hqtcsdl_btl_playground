# P3 — Stage 1-2: Ingest + Filter

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §5.1 Topology stream  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.4 Module contract  
> Prototype: [`playground/ingest/`](../../playground/ingest/) · [`playground/filter/`](../../playground/filter/)  
> Theory: [`docs/theory/ingest.md`](../theory/ingest.md) · [`docs/theory/spam-filter.md`](../theory/spam-filter.md)

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P1 — MongoDB](phase-01-tang-du-lieu-mongodb.md) · [P2 — Redis Streams Runtime](phase-02-runtime-redis-streams.md) |
| **FR liên quan** | **FR-01** (thu thập đa nguồn) · **FR-02** (lọc spam cascade) |
| **Điều hướng** | [← P2](phase-02-runtime-redis-streams.md) · [P4 →](phase-04-ner-sentiment.md) |

---

## 1. Mục tiêu

Port hai stage đầu từ prototype `playground/` vào `src/pipeline/`, wire qua Redis Streams:

- **Stage 1 (Ingest):** Gọi social APIs (Twitter/RapidAPI, Alpha Vantage, Yahoo Finance, Reddit), chuẩn hóa thành `raw_events`, ghi MongoDB.
- **Stage 2 (Filter):** Đọc `raw_events` qua stream, cascade L1 (heuristic) → L2 (rule) → L3 (FastText ML), tách `clean_events` / `dropped_events`.

---

## 2. Công việc & tái sử dụng

### 2.1. Stage 1 — Ingest (`src/pipeline/ingest/`)

**Port từ [`playground/ingest/lib/`](../../playground/ingest/lib/):**

```text
src/pipeline/ingest/
├── __init__.py
├── worker.py          # dùng harness _runtime/worker.py
├── collectors/
│   ├── __init__.py
│   ├── twitter.py     # ← playground/ingest/lib/collectors/twitter.py
│   ├── news_av.py     # ← playground/ingest/lib/collectors/news_av.py
│   ├── news_yahoo.py  # ← playground/ingest/lib/collectors/news_yahoo.py
│   └── reddit.py      # ← playground/ingest/lib/collectors/reddit.py (+ reddit_browser.py)
└── events.py          # ← playground/ingest/lib/events.py (map API → raw_event schema)
```

**`worker.py` ingest** — `processor` function:
1. Đọc kickoff entry từ `stage:ingest:in` (payload: `{coin_id, timeframe, sources}`)
2. Gọi collectors theo `sources` list
3. Chuẩn hóa thành `raw_events` documents (schema §13.4)
4. Ghi MongoDB `raw_events` qua `upsert_stage("raw_events", doc, unique_keys=["source","external_id"])`
5. Trả list docs → harness XADD `stage:filter:in` mỗi doc

**Schema `raw_events` (§13.4):**
```json
{
  "event_id": "uuid",
  "source": "twitter|news|reddit",
  "external_id": "...",
  "raw_text": "...",
  "author_id": "...",
  "metrics": {"likes": 42, "retweets": 10, "followers": 3200000},
  "timestamp": 1714248653,
  "ingested_at": 1716110997
}
```

**Nguồn và API key:**
| Lệnh | Source | API key |
|------|--------|---------|
| `twitter` | `twitter` | `RAPIDAPI_KEY` |
| `news-av` | `news` | `ALPHA_VANTAGE_API_KEY` |
| `news-yahoo` | `news` | Không cần |
| `reddit` | `reddit` | `REDDIT_CLIENT_*` hoặc Playwright |

### 2.2. Stage 2 — Filter (`src/pipeline/filter/`)

**Port từ [`playground/filter/lib/`](../../playground/filter/lib/):**

```text
src/pipeline/filter/
├── __init__.py
├── worker.py          # dùng harness _runtime/worker.py
├── cascade.py         # ← playground/filter/lib/cascade.py (L1→L2→L3 pipeline)
├── heuristic.py       # ← playground/filter/lib/heuristic.py (L1: author flood, URL spam)
├── dedup.py           # ← playground/filter/lib/dedup.py (L1: duplicate clean_text)
└── ml.py              # ← playground/filter/lib/ml.py (L3: FastText P(spam))
```

**Cascade L1 → L2 → L3:**
- **L1 (heuristic):** Author flood, URL spam, short text, duplicate `clean_text` hash
- **L2 (rule):** Từ khóa pump/shill, regex pattern danh sách đen
- **L3 (ML):** FastText `models/spam/spam_model.bin` → `P(spam) ≥ 0.5` → DROP

**`worker.py` filter** — `processor` function:
1. Nhận `raw_event` document từ stream
2. Chạy cascade(raw_event)
3. Nếu PASS: ghi `clean_events`, trả doc để XADD `stage:ner:in`
4. Nếu DROP: ghi `dropped_events` (với `drop_stage`, `drop_reason`, `filter` metadata); trả `[]` (không XADD downstream)

**Schema `clean_events`:**
```json
{
  "event_id": "...",
  "source": "...",
  "clean_text": "...",
  "filter": {
    "stage": "passed",
    "layers": ["L1", "L2", "L3"],
    "fasttext": {"prob_spam": 0.12, "label": "ham"}
  },
  "timestamp": ...,
  "ingested_at": ...
}
```

**Schema `dropped_events`:**
```json
{
  "event_id": "...",
  "drop_stage": "L1|L2|L3",
  "drop_reason": "author_flood|url_spam|pump_keyword|fasttext_spam",
  "filter": {...}
}
```

### 2.3. FastText model

- File: `models/spam/spam_model.bin`
- Train script: `scripts/train_spam.py` (thêm ở P10 nếu cần retrain)
- Nếu model chưa có → fallback chỉ L1+L2

---

## 3. Kiểm thử

| Test ID | Mô tả | Input | Kết quả mong đợi |
|---------|-------|-------|------------------|
| **TC-01** | Filter L1 — spam shill | Tweet pump regex ("🚀🚀 100x BUY NOW!!!") | DROP tại L1, `drop_reason="pump_keyword"` trong `dropped_events` |
| **TC-02** | Filter L3 — FastText | Text train spam model | `P(spam) ≥ 0.5` → DROP, ghi `dropped_events` |
| **TC-09** | Dedup ingest chạy 2 lần | Chạy ingest cùng source + external_id × 2 | Lần 2 `DuplicateKeyError` → skip; `raw_events` không thêm doc |
| T3-01 | Ingest Twitter cơ bản | `sources=["twitter"]`, coin=BTC | ≥ 1 `raw_events` trong MongoDB |
| T3-02 | Ingest Alpha Vantage | `sources=["news-av"]` | ≥ 1 news event với `source="news"` |
| T3-03 | Stream flow ingest→filter | Kickoff entry → stream pipeline | `clean_events` có doc; `stage:filter:in` processed |
| T3-04 | L1 pass bình thường | Tweet hợp lệ tầm thường | PASS L1/L2/L3 → `clean_events` |
| T3-05 | Recall filter (benchmark) | Tập 100 tweet label thủ công | ≥ 85% spam bị DROP |

```bash
# Unit test (không cần MongoDB/Redis)
pytest tests/test_filter.py -v

# Integration test (cần docker compose)
pytest tests/test_ingest_filter_integration.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/pipeline/ingest/` có đủ collectors (twitter, news_av, news_yahoo, reddit)
- [ ] `src/pipeline/filter/` có cascade L1/L2/L3 hoạt động
- [ ] Kickoff entry → `stage:ingest:in` → raw_events → `stage:filter:in` → clean/dropped events chảy qua stream
- [ ] TC-01, TC-02, TC-09 pass
- [ ] T3-01 → T3-04 pass
- [ ] `drop_reason` ghi đúng vào `dropped_events.filter`
- [ ] Recall ≥ 85% trên tập test spam (NFR-01 §4.3.3)
- [ ] Fallback graceful khi thiếu API key (Twitter 403 → log warning; tiếp tục nguồn khác)

---

*[← P2 — Redis Streams Runtime](phase-02-runtime-redis-streams.md) · [P4 — NER + Sentiment →](phase-04-ner-sentiment.md)*
