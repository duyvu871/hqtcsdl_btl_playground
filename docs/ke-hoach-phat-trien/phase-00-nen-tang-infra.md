# P0 — Nền tảng monorepo & Infra

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §4 Stack · §10 Deployment · §10.3 Biến môi trường  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.4 Cấu trúc thư mục sản phẩm

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | — (phase đầu tiên) |
| **FR liên quan** | (nền tảng cho tất cả FR) |
| **Điều hướng** | ← *(đầu)* · [P1 →](phase-01-tang-du-lieu-mongodb.md) |

---

## 1. Mục tiêu

Dựng khung monorepo `src/` + `web/` chạy độc lập, kết nối được **Redis 7** + **MongoDB 7** qua Docker Compose, với config tập trung và package Python cài một lần.

---

## 2. Công việc & tái sử dụng

### 2.1. Cấu trúc thư mục gốc

```text
pyproject.toml
.env.example
docker-compose.yml           # redis:7-alpine + mongo:7 (tối thiểu P0)
config/
├── settings.yaml
├── coin_registry.json       # Top 10 coin + alias
└── prompts/
    └── insight_v1.txt
models/spam/                 # placeholder (spam_model.bin thêm ở P3)
src/
└── common/
    ├── config.py
    ├── redis_client.py
    └── mongo_client.py
tests/
└── test_infra.py
```

### 2.2. File chi tiết cần tạo

**`pyproject.toml`** — gom dependency từ các `playground/*/pyproject.toml`:
- `motor`, `pymongo`, `redis[hiredis]`, `fastapi`, `uvicorn`, `pydantic`, `python-dotenv`
- `ccxt`, `openai` (OpenRouter), `transformers`, `torch`, `polars`, `fasttext`
- `weasyprint`, `pytest`, `httpx`

**`.env.example`** — theo §10.3:
```bash
REDIS_URL=redis://redis:6379/0
MONGODB_URI=mongodb://mongo:27017
MONGODB_DB=crypto_mvp
RAPIDAPI_KEY=...
ALPHA_VANTAGE_API_KEY=...
OPENROUTER_API_KEY=...
OPENROUTER_INSIGHT_MODEL=anthropic/claude-3.5-sonnet
STREAM_MAXLEN=50000
STREAM_CLAIM_IDLE_MS=30000
STREAM_MAX_RETRY=3
SESSION_TTL_DAYS=7
```

**`src/common/config.py`** — gom từ `playground/*/lib/config.py`:
- Load `.env` qua `python-dotenv`
- Expose `settings` object với tất cả biến môi trường có type hint
- Fail fast khi thiếu biến bắt buộc (`MONGODB_URI`, `REDIS_URL`)

**`src/common/redis_client.py`** — gom từ các playground:
- `get_redis()` → `redis.asyncio.Redis` singleton (lazy init)
- Helper `xadd`, `xreadgroup`, `xack`, `hset`, `hgetall` wrap async

**`src/common/mongo_client.py`** — gom từ `playground/*/lib/mongo.py`:
- `get_db()` → `motor.motor_asyncio.AsyncIOMotorDatabase` singleton
- Helper `upsert_stage(collection, doc, unique_keys)` dùng chung cho tất cả stage

**`docker-compose.yml`** (tối thiểu P0):
```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]
```

**`config/coin_registry.json`** — seed Top 10:
```json
{
  "BTC": ["bitcoin", "btc", "$BTC", "BTCUSDT"],
  "ETH": ["ethereum", "eth", "$ETH", "ETHUSDT"],
  "SOL": ["solana", "sol", "$SOL"],
  "BNB": ["bnb", "$BNB"],
  "XRP": ["ripple", "xrp", "$XRP"],
  "ADA": ["cardano", "ada", "$ADA"],
  "DOGE": ["dogecoin", "doge", "$DOGE"],
  "AVAX": ["avalanche", "avax", "$AVAX"],
  "DOT": ["polkadot", "dot", "$DOT"],
  "MATIC": ["polygon", "matic", "$MATIC"]
}
```

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh chạy | Kết quả mong đợi |
|---------|-------|-----------|------------------|
| T0-01 | Docker services healthy | `docker compose up redis mongo -d` | Redis PONG, Mongo OK |
| T0-02 | Config load không lỗi | `pytest tests/test_infra.py::test_config_load` | Không raise exception |
| T0-03 | Redis ping | `pytest tests/test_infra.py::test_redis_ping` | `PONG` |
| T0-04 | MongoDB ping | `pytest tests/test_infra.py::test_mongo_ping` | `{'ok': 1.0}` |
| T0-05 | Import package | `python -c "from src.common.config import settings"` | Không lỗi import |

**Mẫu `tests/test_infra.py`:**
```python
import pytest
from src.common.config import settings
from src.common.redis_client import get_redis
from src.common.mongo_client import get_db

def test_config_load():
    assert settings.MONGODB_URI
    assert settings.REDIS_URL

@pytest.mark.asyncio
async def test_redis_ping():
    r = await get_redis()
    assert await r.ping()

@pytest.mark.asyncio
async def test_mongo_ping():
    db = await get_db()
    result = await db.command("ping")
    assert result["ok"] == 1.0
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `uv sync` (hoặc `pip install -e .`) hoàn thành không lỗi
- [ ] `docker compose up redis mongo` → cả hai service healthy
- [ ] T0-01 → T0-05 pass
- [ ] `.env.example` có đủ tất cả biến §10.3
- [ ] `coin_registry.json` seed 10 coin + alias
- [ ] Lint (`ruff check src/`) pass không lỗi
- [ ] `src/common/` importable từ bất kỳ module con trong `src/`

---

*[← Đầu](README.md) · [P1 — Tầng dữ liệu MongoDB →](phase-01-tang-du-lieu-mongodb.md)*
