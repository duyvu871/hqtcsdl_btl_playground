# P10 — Triển khai, E2E & Hardening

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §10 Triển khai Docker Compose · §10.1 Services · §10.2 Healthcheck · §12 Vận hành  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §4.1 Môi trường phát triển · §4.3 Kiểm thử

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P9 — Frontend React SPA](phase-09-frontend-spa.md) |
| **FR liên quan** | Tất cả FR-01..FR-15 (kiểm chứng cuối) |
| **Điều hướng** | [← P9](phase-09-frontend-spa.md) · *(kết thúc)* |

---

## 1. Mục tiêu

Đóng gói toàn bộ hệ thống vào `docker-compose.yml` đầy đủ (13 service), chạy một lệnh `docker compose up`, kiểm thử E2E end-to-end, benchmark NFR, drain DLQ, và điền số liệu hoàn chỉnh vào báo cáo.

---

## 2. Công việc & tái sử dụng

### 2.1. `docker-compose.yml` đầy đủ (§10.1)

```yaml
services:
  redis:
    image: redis:7-alpine
    ports: ["6379:6379"]
    healthcheck:
      test: ["CMD", "redis-cli", "PING"]
      interval: 5s; timeout: 3s; retries: 5

  mongo:
    image: mongo:7
    ports: ["27017:27017"]
    environment:
      MONGO_INITDB_DATABASE: crypto_mvp
    healthcheck:
      test: ["CMD", "mongosh", "--eval", "db.adminCommand('ping')"]

  api:
    build: .
    command: uvicorn src.api.main:app --host 0.0.0.0 --port 8000
    ports: ["8000:8000"]
    env_file: .env
    depends_on:
      redis: {condition: service_healthy}
      mongo: {condition: service_healthy}

  orchestrator:
    build: .
    command: python -m src.orchestrator
    env_file: .env
    environment: {ROLE: orchestrator}
    depends_on: [api, redis, mongo]

  worker-ingest:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: ingest}
    depends_on: [redis, mongo]

  worker-filter:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: filter}

  worker-ner:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: ner}

  worker-sentiment:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: sentiment}

  worker-influence:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: influence}

  worker-scoring:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: scoring}

  worker-insight:
    build: .
    command: python -m src.pipeline.worker
    env_file: .env
    environment: {STAGE: insight}

  web:
    build:
      context: web
      dockerfile: Dockerfile
    ports: ["3000:80"]
    depends_on: [api]
    environment:
      VITE_API_URL: http://localhost:8000
```

### 2.2. Scripts và tooling vận hành (§12)

**Monitoring commands (§12.2):**
```bash
# Độ dài stream
redis-cli XLEN stage:filter:in

# Consumer group lag
redis-cli XINFO GROUPS stage:filter:in

# Pending entries
redis-cli XPENDING stage:filter:in cg:filter

# Session state
redis-cli HGETALL session:{session_id}:state

# Control stream recent events
redis-cli XRANGE session:{session_id}:events - + COUNT 20
```

**DLQ drain (§12.3):**
```bash
# Đọc DLQ
redis-cli XRANGE stage:filter:dlq - + COUNT 10

# Re-inject vào stream sau sửa lỗi
python scripts/dlq_drain.py --stage filter --limit 10

# Xoá khỏi DLQ sau re-inject
redis-cli XDEL stage:filter:dlq <entry_id>
```

**Replay session (§12.4):**
```bash
python scripts/replay_session.py --session-id <old_id> --new-session
# Đọc từ MongoDB, XADD batch vào stream với session_id mới
```

**Train spam model (§4.1):**
```bash
python scripts/train_spam.py \
  --data data/spam_train.csv \
  --output models/spam/spam_model.bin \
  --epochs 25 --lr 0.1
```

### 2.3. Dockerfile (backend + frontend)

**`Dockerfile` (backend):**
```dockerfile
FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install uv && uv sync --frozen
COPY src/ src/
COPY config/ config/
COPY models/ models/
```

**`web/Dockerfile` (frontend):**
```dockerfile
FROM node:22-alpine AS build
WORKDIR /app
COPY package*.json .
RUN npm ci
COPY src/ src/
COPY index.html vite.config.ts tsconfig*.json .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
```

### 2.4. Benchmark NFR (§4.3.3)

| NFR | Mục tiêu | Script | Cách đo |
|-----|----------|--------|---------|
| NFR-01 | Filter throughput ≥ 500 events/s | `scripts/bench_filter.py` | Đẩy 1000 entries; đo thời gian |
| NFR-02 | Sentiment latency ≤ 2s/event | `scripts/bench_sentiment.py` | FinBERT inference p95 |
| NFR-03 | API OHLCV response ≤ 200ms | `pytest tests/bench_api.py` | 100 requests; p99 latency |

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh | Kết quả mong đợi |
|---------|-------|------|------------------|
| T10-01 | `docker compose up` toàn stack | `docker compose up -d` | Tất cả 13 service healthy |
| T10-02 | Healthcheck API | `GET /api/v1/health` | `{mongodb:"ok", redis:"ok", workers:{...}}` |
| T10-03 | E2E: tạo session → PDF | Playwright TC-10 | Session completed; PDF download |
| T10-04 | Benchmark Filter | `scripts/bench_filter.py` | ≥ 500 events/s |
| T10-05 | Benchmark Sentiment | `scripts/bench_sentiment.py` | p95 ≤ 2s/event |
| T10-06 | DLQ drain | Inject bad entry; drain | Entry re-processed; `dropped_events` | ghi |
| T10-07 | Replay session | `scripts/replay_session.py` | New session chạy từ Mongo data |
| T10-08 | Scale worker filter × 2 | Thêm `worker-filter-2` service | Entries phân phối đều 2 consumer |
| T10-09 | Redis TTL expire | Set `SESSION_TTL_DAYS=0.001` | Sau TTL: WS read-only; MongoDB history OK |
| T10-10 | Tất cả TC-01..TC-10 pass | `pytest tests/ -v` | 10/10 pass |

```bash
# One-command full stack
cp .env.example .env
# Điền API keys
docker compose up -d

# Chạy toàn bộ test suite
pytest tests/ -v --timeout=120

# E2E Playwright
cd web && npx playwright test
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `docker compose up` → 13 service healthy trong < 2 phút
- [ ] `GET /api/v1/health` → tất cả `"ok"`
- [ ] TC-10 E2E Playwright pass: Dashboard → Phân tích → Chat → PDF
- [ ] Tất cả TC-01..TC-10 pass (`pytest tests/ -v`)
- [ ] Benchmark NFR-01 (filter ≥ 500/s) + NFR-02 (sentiment p95 ≤ 2s) đạt
- [ ] DLQ drain script hoạt động
- [ ] Replay session hoạt động với session_id mới
- [ ] **Bảng FR hoàn chỉnh** — điền % hoàn thành thực tế vào §4.4.3 báo cáo
- [ ] **Bảng test results** — điền số liệu thực tế vào §4.3.3 báo cáo
- [ ] README hướng dẫn deploy một lệnh từ clone đến chạy

---

## 5. Lệnh demo nhanh (sau khi hoàn thành P10)

```bash
# 1. Clone và setup
git clone <repo> && cd hqtcsdl_btl_new
cp .env.example .env  # điền RAPIDAPI_KEY, OPENROUTER_API_KEY, ...

# 2. Chạy toàn bộ stack
docker compose up -d

# 3. Truy cập
# Dashboard:   http://localhost:3000/dashboard
# ETL Monitor: http://localhost:3000/etl
# API Docs:    http://localhost:8000/docs

# 4. Hoặc CLI trigger pipeline
curl -X POST http://localhost:8000/api/v1/analysis/sessions \
  -H "Content-Type: application/json" \
  -d '{"coin_id":"BTC","timeframe":"1h"}'
```

---

*[← P9 — Frontend React SPA](phase-09-frontend-spa.md) · [Về README](README.md)*
