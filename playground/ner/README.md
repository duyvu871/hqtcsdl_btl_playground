# NER — Stage 3 (Entity Recognition & Coin Mapping)

Gán **`coin_id`** cho social/news events và **fan-out** 1 post → N message (mỗi coin một bản ghi). Đọc từ `clean_events` (hoặc `raw_events` khi dev) → ghi `mapped_events`.

**Cơ sở lý thuyết:** [`docs/theory/ner-mapping.md`](../../docs/theory/ner-mapping.md)

**3 chế độ** qua OpenRouter LLM + rules:

| Mode | Luồng |
| --- | --- |
| **`hybrid`** | Rules (cashtag, alias, metadata) trước; gọi LLM khi **0 mention** nhưng text crypto-related, hoặc **ambiguous** |
| **`validator`** | Rules chạy trước; **LLM luôn** xác nhận/sửa danh sách mention |
| **`full`** | **Chỉ LLM** — rules không quyết định output |

Tham chiếu: [`docs/pipeline-overview.md`](../../docs/pipeline-overview.md) § Bước 3 · [`docs/lunacrush-data-flow.md`](../../docs/lunacrush-data-flow.md) § Bước 3

---

## Kiến trúc

```text
clean_events (hoặc raw_events)
       │
       ▼
  Coin registry (Top 10 MVP)
       │
       ├── rules: $BTC, alias, Yahoo related_tickers
       │
       ├── LLM (OpenRouter, model từ .env)  ← hybrid / validator / full
       │
       ▼
  fan-out → mapped_events  (1 row / parent_event_id × coin_id)
       │
       ▼
  Stage 4 Sentiment
```

---

## Setup

```bash
# MongoDB + API keys chung
cd playground/ingest
cp .env.example .env   # MONGODB_URI

# OpenRouter
cd ../ner
cp .env.example .env
# OPENROUTER_API_KEY, OPENROUTER_MODEL

uv sync
```

Biến `MONGODB_*` load từ **`playground/ingest/.env`**, override bằng **`playground/ner/.env`**.

---

## Chạy

```bash
cd playground/ner

# Thống kê
uv run python run.py stats

# Hybrid — rules only nếu không cần LLM; LLM khi ambiguous
uv run python run.py --mode hybrid --input raw --dry-run -v --limit 30

# Validator — LLM xác nhận mọi event
uv run python run.py --mode validator --input raw --dry-run --limit 10

# Full LLM
uv run python run.py --mode full --input raw --dry-run --limit 5

# Ghi thật (input clean sau Stage 2)
uv run python run.py --mode hybrid --limit 100
```

### CLI

| Flag | Mặc định | Mô tả |
| --- | --- | --- |
| `--mode` | `NER_MODE` env | `hybrid` \| `validator` \| `full` |
| `--input` | `clean` | `clean` = clean_events; `raw` = raw_events (dev) |
| `--limit` | 100 | Số event tối đa |
| `--dry-run` | — | Không ghi MongoDB |
| `--source` | all | `twitter` \| `reddit` \| `news` |

---

## Biến môi trường

| Biến | Bắt buộc | Mô tả |
| --- | --- | --- |
| `MONGODB_URI` | Có | Từ ingest `.env` |
| `OPENROUTER_API_KEY` | Có (validator/full; hybrid khi cần LLM) | [openrouter.ai/keys](https://openrouter.ai/keys) |
| `OPENROUTER_MODEL` | Có (khi dùng LLM) | VD: `google/gemini-2.0-flash-001`, `openai/gpt-4o-mini` |
| `OPENROUTER_BASE_URL` | Không | Mặc định `https://openrouter.ai/api/v1` |
| `OPENROUTER_SITE_URL` | Không | HTTP-Referer (OpenRouter ranking) |
| `OPENROUTER_APP_NAME` | Không | X-Title header |
| `NER_MODE` | Không | `hybrid` \| `validator` \| `full` |
| `MONGODB_MAPPED_COLLECTION` | Không | Output: `mapped_events` |
| `COIN_REGISTRY_PATH` | Không | JSON registry Top 10 |

LLM qua **[OpenAI Python SDK](https://github.com/openai/openai-python)** (`openai` package), `base_url` trỏ OpenRouter.

---

## Output — `mapped_events`

```json
{
  "mapped_id": "uuid",
  "parent_event_id": "550e8400-...",
  "coin_id": "BTC",
  "clean_text": "JUST IN: SEC says #BITCOIN ...",
  "author_id": "...",
  "timestamp": 1714248653,
  "ner": {
    "mode": "hybrid",
    "method": "cashtag",
    "evidence": "$BTC",
    "confidence": 1.0,
    "used_llm": false,
    "notes": "hybrid_rules_only"
  },
  "mapped_at": 1716113000
}
```

Unique index: `(parent_event_id, coin_id)`.

---

## Coin registry

File [`data/coin_registry.json`](data/coin_registry.json): Top 10 MVP — BTC, ETH, SOL, BNB, XRP, ADA, DOGE, AVAX, DOT, LINK + aliases.

Yahoo news: dùng `related_tickers` / `link_meta.symbol` từ ingest Stage 1.

---

## Ghi chú mode

**Hybrid** — tiết kiệm token; LLM chỉ khi rules không đủ hoặc cashtag lạ / text crypto mà không map được.

**Validator** — cân bằng cost/accuracy; phù hợp review batch trước production.

**Full** — tốn token nhất; dùng khi text dài, ngữ cảnh phức tạp, ít cashtag.

---

## Bước tiếp theo

- Stage 4 sentiment: đọc `mapped_events` theo `coin_id`
- Tune registry aliases; thêm contract address (nâng cao)
