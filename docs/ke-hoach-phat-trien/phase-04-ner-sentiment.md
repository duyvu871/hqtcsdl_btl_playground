# P4 — Stage 3-4: NER + Sentiment

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §5.1 Topology · §5.7 Fan-out Stage 3  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.2 mapped_events/sentiment_events  
> Prototype: [`playground/ner/`](../../playground/ner/) · [`playground/sentiment/`](../../playground/sentiment/)  
> Theory: [`docs/theory/ner-mapping.md`](../theory/ner-mapping.md)

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P3 — Ingest + Filter](phase-03-ingest-filter.md) |
| **FR liên quan** | **FR-03** (NER map coin Top 10 + fan-out) · **FR-04** (Sentiment FinBERT per coin-event) |
| **Điều hướng** | [← P3](phase-03-ingest-filter.md) · [P5 →](phase-05-influence-scoring.md) |

---

## 1. Mục tiêu

- **Stage 3 (NER):** Mỗi `clean_event` được map sang N `mapped_events` (fan-out) — mỗi coin được đề cập = 1 document riêng. Dùng hybrid: cashtag rule → registry matching → LLM fallback (OpenRouter).
- **Stage 4 (Sentiment):** Chấm sentiment per coin-event qua FinBERT; sinh `sentiment_score` ∈ [-1,1] và `sentiment_label` (positive/neutral/negative).

---

## 2. Công việc & tái sử dụng

### 2.1. Stage 3 — NER (`src/pipeline/ner/`)

**Port từ [`playground/ner/lib/`](../../playground/ner/lib/):**

```text
src/pipeline/ner/
├── __init__.py
├── worker.py          # dùng harness; trả list mapped_events (fan-out)
├── rules.py           # ← playground/ner/lib/rules.py (cashtag $BTC, keyword match)
├── registry.py        # ← playground/ner/lib/registry.py (load coin_registry.json)
├── llm.py             # ← playground/ner/lib/llm.py (OpenRouter fallback khi rules miss)
└── pipeline.py        # ← playground/ner/lib/pipeline.py (hybrid: rules → registry → llm)
```

**Chiến lược hybrid (§3.3.4):**
1. **Cashtag rule:** Match regex `\$[A-Z]{2,10}` → map ngay từ registry
2. **Keyword match:** Alias lowercase (bitcoin, eth, …) → `coin_id`
3. **LLM fallback:** Chỉ gọi OpenRouter khi rules không map được và text > 20 từ

**Fan-out — 1 `clean_event` → N `mapped_events`:**
```python
# Nếu tweet đề cập BTC và ETH → 2 mapped_events riêng
outputs = []
for coin_id, ner_meta in detected_coins:
    outputs.append({
        "mapped_id": str(uuid4()),
        "parent_event_id": clean_event["event_id"],
        "coin_id": coin_id,
        "clean_text": clean_event["clean_text"],
        "ner": {"method": "cashtag|keyword|llm", "confidence": 0.95},
        "source": clean_event["source"],
        "timestamp": clean_event["timestamp"],
    })
return outputs  # harness XADD mỗi item lên stage:sentiment:in
```

**Idempotent:** Unique index `(parent_event_id, coin_id)` → upsert an toàn nếu chạy lại.

### 2.2. Stage 4 — Sentiment (`src/pipeline/sentiment/`)

**Port từ [`playground/sentiment/lib/`](../../playground/sentiment/lib/):**

```text
src/pipeline/sentiment/
├── __init__.py
├── worker.py          # dùng harness
├── scorer.py          # ← playground/sentiment/lib/scorer.py (FinBERT + rule_based)
├── rule_based.py      # ← playground/sentiment/lib/rule_based.py (bullish/bearish keywords)
├── schema.py          # ← playground/sentiment/lib/schema.py (builder sentiment_events)
└── utils.py           # ← playground/sentiment/lib/utils.py
```

**Sửa L-01 (BUG-04):** Propagate đầy đủ metadata filter + ner sang `sentiment_events`:
```python
# schema.py — thêm fields
{
    "sentiment_id": str(uuid4()),
    "mapped_id": doc["mapped_id"],
    "coin_id": doc["coin_id"],
    "sentiment_score": score,       # float [-1, 1]
    "sentiment_label": label,       # "positive" | "neutral" | "negative"
    "probabilities": {"pos": 0.8, "neu": 0.15, "neg": 0.05},
    "method": "finbert|rule_based|av_bypass",
    "filter_meta": doc.get("filter"),   # ← L-01: propagate từ clean_event
    "ner_meta": doc.get("ner"),         # ← L-01: propagate từ mapped_event
    "source": doc["source"],
    "timestamp": doc["timestamp"],
}
```

**Alpha Vantage bypass:** Nếu `source="news"` và Alpha Vantage đã trả sentiment → dùng ngay (`method="av_bypass"`), không gọi FinBERT.

**Rule-based fallback:** Khi FinBERT unavailable (no GPU) → dùng bullish/bearish keyword list.

---

## 3. Kiểm thử

| Test ID | Mô tả | Input | Kết quả mong đợi |
|---------|-------|-------|------------------|
| **TC-03** | NER cashtag `$BTC` | `"Buy $BTC now"` | `coin_id="BTC"`, `ner.method="cashtag"` |
| **TC-04** | Sentiment bullish | `"BTC to the moon bullish breakout"` | `score > 0`, `label="positive"` |
| **TC-05** | Sentiment bearish | `"ETH crash dump rekt"` | `score < 0`, `label="negative"` |
| T4-01 | Fan-out 2 coin | Tweet đề cập BTC và ETH | 2 `mapped_events` với `parent_event_id` như nhau |
| T4-02 | Fan-out idempotent | Chạy NER lại trên cùng `clean_event` | Không tạo thêm doc (upsert) |
| T4-03 | NER keyword | `"bitcoin looking strong"` | `coin_id="BTC"`, `method="keyword"` |
| T4-04 | Metadata L-01 | `sentiment_events` sau filter | Có field `filter_meta` và `ner_meta` không null |
| T4-05 | Test scorer unit | `playground/sentiment/tests/test_scorer.py` | 5/5 pass (positive, negative, neutral, empty, mixed) |

```bash
# Unit test (không cần services)
cd playground/sentiment && uv run python tests/test_scorer.py

# Unit test từ src/
pytest tests/test_ner.py tests/test_sentiment.py -v

# Integration (cần services)
pytest tests/test_ner_sentiment_integration.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/pipeline/ner/` hybrid (cashtag → keyword → LLM fallback) hoạt động
- [ ] Fan-out: 1 clean_event → N mapped_events (N = số coin phát hiện)
- [ ] `mapped_events` unique `(parent_event_id, coin_id)` — không duplicate
- [ ] `src/pipeline/sentiment/` ghi `sentiment_events` với score + label + probabilities
- [ ] L-01 sửa: `filter_meta` và `ner_meta` propagate sang `sentiment_events`
- [ ] TC-03, TC-04, TC-05 pass
- [ ] `test_scorer.py` 5/5 pass
- [ ] Precision NER mục tiêu ≥ 90% trên cashtag rõ (§4.3.3)
- [ ] Alpha Vantage bypass hoạt động khi `source="news"` có `av_sentiment`

---

*[← P3 — Ingest + Filter](phase-03-ingest-filter.md) · [P5 — Influence + Scoring →](phase-05-influence-scoring.md)*
