# P5 — Stage 5-6: Influence + Scoring

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §5.1 (ghi chú Stage 5→6)  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.2 influence_aggregates / scoring_signals  
> Prototype: [`playground/influence/`](../../playground/influence/) · [`playground/scoring/`](../../playground/scoring/)

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P4 — NER + Sentiment](phase-04-ner-sentiment.md) |
| **FR liên quan** | **FR-05** (Influence weight + aggregate) · **FR-06** (Galaxy Alpha/Safety dual-score) · **FR-07** (OHLCV Binance CCXT) |
| **Điều hướng** | [← P4](phase-04-ner-sentiment.md) · [P6 →](phase-06-orchestrator.md) |

---

## 1. Mục tiêu

- **Stage 5 (Influence):** Tính trọng số ảnh hưởng mỗi event (log-log model), aggregate thành `influence_aggregates` theo cửa sổ thời gian + coin + timeframe.
- **Stage 6 (Scoring):** Join `influence_aggregates` + OHLCV Binance CCXT, tính **Galaxy Alpha Score** và **Galaxy Safety Score** (dual-score v2.1), emit signal BUY/HOLD.

---

## 2. Công việc & tái sử dụng

### 2.1. Stage 5 — Influence (`src/pipeline/influence/`)

**Port từ [`playground/influence/lib/`](../../playground/influence/lib/):**

```text
src/pipeline/influence/
├── __init__.py
├── worker.py          # dùng harness; ghi aggregates → XADD batch-trigger
├── scoring.py         # ← playground/influence/lib/scoring.py (log-log weight)
├── aggregate.py       # ← playground/influence/lib/aggregate.py (window rollup)
└── schema.py          # ← playground/influence/lib/schema.py
```

**Luồng xử lý (§5.1 ghi chú Stage 5→6):**
1. Nhận `sentiment_event` từ `stage:influence:in`
2. Tính `influence_weight` (log-log model từ metrics.followers, likes, retweets)
3. Ghi `weighted_events` (per-event)
4. Upsert `influence_aggregates` (per window: `coin_id + timeframe + window_start`)
5. Khi đủ batch (hoặc timeout window) → XADD **batch-trigger entry** vào `stage:scoring:in`

> Downstream (Stage 6) **không đọc Mongo** để lấy input — nhận đủ context qua entry transport.

**Schema `influence_aggregates` (input chuẩn cho Stage 6):**
```json
{
  "coin_id": "BTC",
  "timeframe": "1h",
  "window_start": 1714248000,
  "sentiment_score": 0.42,
  "social_volume": 1250,
  "total_influence": 38420.5,
  "weighted_sentiment": 0.61,
  "event_count": 87
}
```

**Log-log influence model (từ playground/influence):**
```python
# scoring.py
def calc_influence_weight(metrics: dict) -> float:
    followers = max(metrics.get("followers", 1), 1)
    likes     = max(metrics.get("likes", 0), 0)
    retweets  = max(metrics.get("retweets", 0), 0)
    return (
        math.log1p(followers) * 0.5 +
        math.log1p(likes)     * 0.3 +
        math.log1p(retweets)  * 0.2
    )
```

### 2.2. Stage 6 — Scoring (`src/pipeline/scoring/`)

**Port từ [`playground/scoring/lib/`](../../playground/scoring/lib/):**

```text
src/pipeline/scoring/
├── __init__.py
├── worker.py          # dùng harness; gọi CCXT; emit signal_ready
├── transformer.py     # ← playground/scoring/lib/transformer.py (log-return, Z-score, OLS slope)
├── ortho.py           # ← playground/scoring/lib/ortho.py (PCA orthogonalize)
├── score.py           # ← playground/scoring/lib/score.py (Galaxy Alpha/Safety)
├── rules.py           # ← playground/scoring/lib/rules.py (fractal swing, KL divergence, BUY/HOLD rule)
└── market.py          # ← playground/scoring/lib/market.py (CCXT Binance OHLCV)
```

**Dual-score (từ playground/scoring README):**
- **Galaxy Alpha Score™** = `100 / (1 + exp(-H_t))` — cơ hội (Sigmoid-scaled)
- **Galaxy Safety Score™** = Alpha × `exp(-λ × Z_vol)` — điều chỉnh rủi ro (CARA penalty)
- Rule: `alpha > 60 AND safety > 40` → **BUY**; ngược lại → **HOLD**

**L-02 — Persist OHLCV (khuyến nghị):**  
Thêm collection `market_ohlcv` để cache; tránh gọi CCXT mỗi lần scoring (BUG-05). Nếu cache hit → dùng cache; miss → gọi CCXT.

**L-03 — Tích hợp KL divergence / fractal vào rule engine (BUG-06):**
```python
# rules.py — cập nhật rule engine
def decide_action(alpha, safety, kl_div, fractal_confirmed):
    if alpha > 60 and safety > 40:
        if kl_div > 0.5 and not fractal_confirmed:
            return "HOLD"  # Tín hiệu mâu thuẫn
        return "BUY"
    return "HOLD"
```

**Schema `scoring_signals`:**
```json
{
  "signal_id": "uuid",
  "coin_id": "BTC",
  "timeframe": "1h",
  "action": "BUY",
  "metrics": {
    "galaxy_alpha_score": 68.2,
    "galaxy_safety_score": 55.1,
    "kl_divergence": 0.42,
    "confidence": 95.8
  },
  "execution": {
    "target_price": 70350.0,
    "stop_loss": 65660.0
  },
  "timestamp": 1714248653
}
```

---

## 3. Kiểm thử

| Test ID | Mô tả | Input | Kết quả mong đợi |
|---------|-------|-------|------------------|
| **TC-06** | Influence weight Twitter verified high RT | `{followers:3M, likes:749, retweets:113}` | `0 < influence_weight ≤ 20`; fields đầy đủ |
| **TC-07** | Scoring mock bullish divergence | `playground/scoring/test/run.py::bullish_divergence` | Alpha > 60, Safety > 40 → **BUY** |
| **TC-08** | Scoring mock high volatility panic | `playground/scoring/test/run.py::high_volatility_panic` | Safety thấp → **HOLD** |
| T5-01 | `influence_aggregates` schema | Insert window + check fields | `coin_id`, `timeframe`, `window_start`, `sentiment_score`, `social_volume` đủ |
| T5-02 | Fail-fast < 15 nến | Join OHLCV với < 15 candles | Exception với log rõ ràng; không ghi signal (BUG-03) |
| T5-03 | Batch trigger sang scoring | Window hoàn tất → XADD | Entry xuất hiện trên `stage:scoring:in` |
| T5-04 | `signal_ready` emit | Scoring hoàn tất | Control stream có `event_type=signal_ready` với action |
| T5-05 | Scoring mock 3/3 | Tất cả mock scenarios | bullish, bearish, panic → đúng action |

```bash
# Mock scenarios (không cần services)
cd playground/scoring && uv run python test/run.py

# Unit tests (không cần services)
pytest tests/test_influence.py tests/test_scoring.py -v

# Integration
pytest tests/test_influence_scoring_integration.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/pipeline/influence/` tính `influence_weight` log-log và ghi `weighted_events` + `influence_aggregates`
- [ ] Batch-trigger XADD đúng contract (không đọc Mongo ở Stage 6 để lấy input)
- [ ] `src/pipeline/scoring/` tính Galaxy dual-score (Alpha + Safety) và emit BUY/HOLD
- [ ] L-02: collection `market_ohlcv` persist OHLCV (hoặc cache layer)
- [ ] L-03: KL divergence + fractal ảnh hưởng quyết định action trong `rules.py`
- [ ] TC-06, TC-07, TC-08 pass
- [ ] Scoring mock 3/3 pass (bullish, bearish, high_volatility)
- [ ] BUG-03: fail-fast khi < 15 nến join
- [ ] `scoring_signals` emit `signal_ready` lên control stream

---

*[← P4 — NER + Sentiment](phase-04-ner-sentiment.md) · [P6 — Orchestrator →](phase-06-orchestrator.md)*
