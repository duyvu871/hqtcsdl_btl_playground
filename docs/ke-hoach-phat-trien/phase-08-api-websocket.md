# P8 — FastAPI REST + WebSocket

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §7 Kiến trúc realtime UI · §7.3 WS Broadcaster mã giả  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.3 Thiết kế API (bảng endpoint đầy đủ)

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P6 — Orchestrator](phase-06-orchestrator.md) · [P7 — LLM Insight + PDF](phase-07-insight-pdf.md) |
| **FR liên quan** | **FR-10** (trigger pipeline từ API) · **FR-11** (market OHLCV/ticker) · **FR-12** (WS chat) · **FR-13** (session history) · **FR-14** (PDF endpoint) · **FR-15** (ETL monitor WS) |
| **Điều hướng** | [← P7](phase-07-insight-pdf.md) · [P9 →](phase-09-frontend-spa.md) |

---

## 1. Mục tiêu

Expose toàn bộ REST API + WebSocket của hệ thống qua **FastAPI** (Uvicorn), cho phép frontend React và CLI tương tác với pipeline, session chat, market data và PDF export.

---

## 2. Công việc & tái sử dụng

### 2.1. Cấu trúc module

```text
src/api/
├── main.py               # FastAPI app + CORS + mount router
├── routes/
│   ├── market.py         # /api/v1/market/ohlcv, /ticker
│   ├── analysis.py       # /api/v1/analysis/sessions (CRUD + export)
│   └── pipeline.py       # /api/v1/pipeline/run, /jobs, /stats, /health
├── ws/
│   ├── analysis.py       # /ws/analysis/{session_id}
│   └── pipeline.py       # /ws/pipeline
└── services/
    ├── pdf_export.py      # (từ P7)
    └── market_service.py  # CCXT wrapper
```

### 2.2. REST Endpoints (§3.3.3)

**Dashboard TradingView:**
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| GET | `/api/v1/market/ohlcv` | OHLCV cho chart (`coin`, `interval`, `limit`) |
| GET | `/api/v1/market/ticker` | Giá realtime (`coin`) → `{last, change_pct, volume}` |
| GET | `/api/v1/analysis/sessions` | Lịch sử session (sidebar) |

**Chat phân tích:**
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/v1/analysis/sessions` | Tạo session + trigger orchestrator → `{session_id, job_id}` |
| GET | `/api/v1/analysis/sessions/{id}` | Metadata + Redis state snapshot |
| GET | `/api/v1/analysis/sessions/{id}/messages` | Lịch sử chat từ MongoDB |
| POST | `/api/v1/analysis/sessions/{id}/messages` | Follow-up question |
| GET | `/api/v1/analysis/sessions/{id}/export/pdf` | `application/pdf` |
| GET | `/api/v1/coins/{coin_id}/signal` | Signal card `?timeframe=1h` |

**ETL Monitor:**
| Method | Endpoint | Mô tả |
|--------|----------|-------|
| POST | `/api/v1/pipeline/run` | Trigger batch (retry/Run All) |
| GET | `/api/v1/pipeline/jobs` | Danh sách job gần đây |
| GET | `/api/v1/pipeline/jobs/{job_id}` | Chi tiết job + stage runs |
| GET | `/api/v1/pipeline/stats` | Thống kê collection counts |
| GET | `/api/v1/health` | Health check (mongodb, redis, workers) |

### 2.3. WebSocket Analysis (`src/api/ws/analysis.py`)

Port mã giả §7.3 — catch-up + live:

```python
@router.websocket("/ws/analysis/{session_id}")
async def analysis_ws(ws: WebSocket, session_id: str, last_id: str = "0"):
    await ws.accept()
    stream = f"session:{session_id}:events"

    # Phase 1: catch-up từ last_id
    entries = await redis.xrange(stream, last_id, "+", count=500)
    for entry_id, fields in entries:
        await ws.send_json(envelope(entry_id, fields))
        last_id = entry_id

    # Phase 2: live loop
    while True:
        try:
            batches = await redis.xread({stream: last_id}, block=10_000, count=50)
            if batches:
                for entry_id, fields in batches[0][1]:
                    await ws.send_json(envelope(entry_id, fields))
                    last_id = entry_id
        except WebSocketDisconnect:
            break
```

**Mapping event_type → UI (§7.2):**
| event_type | Component frontend |
|------------|-------------------|
| `planning_step` | `PlanningSteps.tsx` |
| `stage_started` / `stage_progress` | `EtlProgressCard.tsx` |
| `stage_completed` | Card check + stats |
| `stage_failed` | Error bubble |
| `signal_ready` | `SignalCard.tsx` |
| `llm_token` | Markdown stream append |
| `report_done` | Nút Tải PDF |
| `session_completed` | Disable input / done badge |

### 2.4. WebSocket Pipeline (`src/api/ws/pipeline.py`)

```python
@router.websocket("/ws/pipeline")
async def pipeline_ws(ws: WebSocket):
    # Broadcast job events từ tất cả session
    # Subscribe pattern: XREAD multiple control streams
    # Events: job_started, stage_progress, stage_completed, insight_completed
```

### 2.5. Reconnect và mở lại session cũ (§6.5)

```
GET /api/v1/analysis/sessions/{id}/messages
  → render full history từ MongoDB chat_messages

WS connect với ?last_id={last_event_id}
  → catch-up events còn thiếu từ Redis (nếu TTL chưa hết)
  → Nếu Redis expired → chỉ MongoDB history read-only
```

### 2.6. `src/api/main.py`

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Crypto Social Intelligence API")
app.add_middleware(CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"], allow_headers=["*"],
)

app.include_router(market_router,   prefix="/api/v1")
app.include_router(analysis_router, prefix="/api/v1")
app.include_router(pipeline_router, prefix="/api/v1")
app.include_router(ws_analysis_router)
app.include_router(ws_pipeline_router)
```

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh | Kết quả mong đợi |
|---------|-------|------|------------------|
| T8-01 | Health check | `GET /api/v1/health` | `{mongodb: "ok", redis: "ok"}` HTTP 200 |
| T8-02 | Tạo session | `POST /api/v1/analysis/sessions` | HTTP 201, body `{session_id, job_id}` |
| T8-03 | Session messages | `GET /api/v1/analysis/sessions/{id}/messages` | List `chat_messages` đúng thứ tự |
| T8-04 | PDF endpoint | `GET /api/v1/analysis/sessions/{id}/export/pdf` | `Content-Type: application/pdf` |
| T8-05 | Signal card | `GET /api/v1/coins/BTC/signal?timeframe=1h` | JSON với `action`, `metrics`, `execution` |
| T8-06 | OHLCV datafeed | `GET /api/v1/market/ohlcv?coin=BTC&interval=1h` | Array `[{time,open,high,low,close,volume}]` |
| T8-07 | WS catch-up | Connect `?last_id=0` → nhận events đã qua | Tất cả events từ 0 đến hiện tại |
| T8-08 | WS live | Connect; worker emit event | Event xuất hiện qua WS < 1s |
| T8-09 | WS reconnect | Disconnect + reconnect `?last_id=X` | Nhận đúng events sau X |
| T8-10 | CORS header | Request từ localhost:3000 | Header `Access-Control-Allow-Origin` |

```bash
# API test
pytest tests/test_api.py -v

# Chạy API locally
uvicorn src.api.main:app --reload --port 8000
# Swagger: http://localhost:8000/docs
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] Tất cả endpoint bảng §3.3.3 hoạt động
- [ ] OpenAPI `/docs` accessible và đúng schema
- [ ] WS `/ws/analysis/{session_id}` catch-up + live + reconnect `?last_id=` hoạt động
- [ ] WS `/ws/pipeline` broadcast job events
- [ ] CORS allow `http://localhost:3000`
- [ ] `POST /analysis/sessions` trigger orchestrator, trả `{session_id, job_id}`
- [ ] PDF endpoint trả đúng `Content-Type: application/pdf`
- [ ] T8-01 → T8-10 pass

---

*[← P7 — LLM Insight + PDF](phase-07-insight-pdf.md) · [P9 — Frontend React SPA →](phase-09-frontend-spa.md)*
