# P2 — Khung runtime Redis Streams

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §5 Luồng dữ liệu · §5.6 Consumer group & retry · §13.2 Stage worker mã giả  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.1 Nguyên tắc thiết kế module

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P0 — Nền tảng](phase-00-nen-tang-infra.md) |
| **FR liên quan** | Harness cho tất cả FR; trực tiếp: FR-10 (orchestrator), FR-15 (ETL monitor) |
| **Điều hướng** | [← P0](phase-00-nen-tang-infra.md) · [P3 →](phase-03-ingest-filter.md) |

---

## 1. Mục tiêu

Xây dựng **harness worker chung** (`src/pipeline/_runtime/`) hiện thực toàn bộ vòng đời một entry Redis Streams: đọc XREADGROUP → xử lý → ghi MongoDB → XADD downstream → XACK. Bao gồm cơ chế reclaim (XCLAIM), DLQ, và control bus `session:{id}:events`.

---

## 2. Công việc & tái sử dụng

### 2.1. Cấu trúc module

```text
src/pipeline/_runtime/
├── __init__.py
├── worker.py          # vòng lặp chính: XREADGROUP → process → ack
├── emit.py            # helper emit control events vào session:{id}:events
└── keys.py            # hằng tên stream, group, TTL
```

### 2.2. Topology stream (§5.1)

```
stage:ingest:in   → cg:ingest   → stage:filter:in
stage:filter:in   → cg:filter   → stage:ner:in
stage:ner:in      → cg:ner      → stage:sentiment:in
stage:sentiment:in → cg:sentiment → stage:influence:in
stage:influence:in → cg:influence → stage:scoring:in
stage:scoring:in  → cg:scoring  → stage:insight:in
stage:insight:in  → cg:insight  → (không có downstream)

stage:{name}:dlq  — Dead-letter sau max retry
session:{id}:events — Control bus (planning, progress, completed, failed, llm_token, report_done)
session:{id}:state  — Redis Hash runtime counters
```

### 2.3. `src/pipeline/_runtime/keys.py`

```python
STAGE_ORDER = ["ingest", "filter", "ner", "sentiment", "influence", "scoring", "insight"]
NEXT_STREAM = {
    "ingest": "stage:filter:in",
    "filter": "stage:ner:in",
    "ner": "stage:sentiment:in",
    "sentiment": "stage:influence:in",
    "influence": "stage:scoring:in",
    "scoring": "stage:insight:in",
    "insight": None,
}
IN_STREAM  = lambda stage: f"stage:{stage}:in"
DLQ_STREAM = lambda stage: f"stage:{stage}:dlq"
GROUP      = lambda stage: f"cg:{stage}"
CTL_STREAM = lambda sid:   f"session:{sid}:events"
STATE_KEY  = lambda sid:   f"session:{sid}:state"
MAXLEN = 50_000
```

### 2.4. `src/pipeline/_runtime/emit.py` (từ §13.2)

```python
async def emit(redis, session_id: str, event_type: str, data: dict):
    stream = f"session:{session_id}:events"
    await redis.xadd(
        stream,
        {"event_type": event_type, "session_id": session_id,
         "data": json.dumps(data), "ts": utcnow()},
        maxlen=10_000, approximate=True,
    )
```

### 2.5. `src/pipeline/_runtime/worker.py` (từ §13.2)

Vòng lặp chính triển khai **at-least-once** (XACK chỉ sau persist Mongo + XADD downstream):

```python
async def run(stage: str, processor: Callable):
    # Tạo consumer group (idempotent mkstream)
    # Loop: XREADGROUP BLOCK 5000 COUNT 64
    # Mỗi entry:
    #   emit stage_started
    #   outputs = await processor(payload, fields)
    #   for doc in outputs: await mongo.upsert_stage(stage, doc)
    #   if next_stream: XADD next_stream entries
    #   XACK
    #   emit stage_completed (records_in=1, records_out=len(outputs))
    #   HINCRBY session:state {stage}_out len(outputs)
    # Exception: handle_retry_or_dlq (max 3 lần → DLQ)
```

**Cơ chế reclaim PEL (Pending Entry List):**
```python
async def reclaim_pending(stage: str):
    # XAUTOCLAIM stage:in group consumer 30000 0-0 COUNT 10
    # Entries idle > 30s → nhận lại để retry
    # Sau STREAM_MAX_RETRY lần → XADD dlq; XACK
```

### 2.6. Schema entry transport (§5.3)

Mỗi entry trên `stage:*:in` flat string fields:
```
session_id    — UUID
job_id        — string
trace_id      — UUID
produced_by   — "stage:{name}" | "orchestrator"
produced_at   — ISO8601
schema_version — "v1"
payload       — JSON string (business payload)
retry_count   — int (tăng khi reclaim)
```

### 2.7. Control events (§5.4)

| event_type | Emitter | Payload chính |
|------------|---------|---------------|
| `stage_started` | Worker | `{stage}` |
| `stage_progress` | Worker | `{stage, pct, records_in, records_out}` |
| `stage_completed` | Worker | `{stage, records_in, records_out}` |
| `stage_failed` | Worker | `{stage, error}` |
| `planning_step` | Orchestrator | `{step, title, description}` |
| `signal_ready` | Worker Scoring | `{action, alpha, safety, target, stop}` |
| `llm_token` | Worker Insight | `{token}` |
| `report_done` | Worker Insight | `{report_id, pdf_url}` |
| `session_completed` | Orchestrator | `{}` |
| `session_failed` | Orchestrator | `{error}` |

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh | Kết quả mong đợi |
|---------|-------|------|------------------|
| T2-01 | Dummy echo stage: publish→consume→ack | `pytest tests/test_runtime.py::test_echo_stage` | Entry xử lý; `XPENDING` = 0 sau ack |
| T2-02 | Fan-out: 1 input → N outputs | Processor trả list 3 items | 3 entries xuất hiện trên downstream stream |
| T2-03 | DLQ sau max retry | Processor raise Exception mọi lần | Entry vào `stage:test:dlq` sau 3 lần |
| T2-04 | XCLAIM reclaim entry treo | Simulate entry idle > 30s | Worker 2 nhận được entry; xử lý thành công |
| T2-05 | Hash counters cập nhật | Chạy echo stage | `HGETALL session:{id}:state` có `echo_out=N` |
| T2-06 | Control events emit đúng | Chạy echo stage | Stream `session:{id}:events` có `stage_started`, `stage_completed` |

```bash
pytest tests/test_runtime.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/pipeline/_runtime/` chứa `worker.py`, `emit.py`, `keys.py`
- [ ] Dummy echo stage chạy end-to-end: XREADGROUP → process → XADD downstream → XACK
- [ ] Fan-out list outputs hoạt động (1 input → N downstream entries)
- [ ] Exception → DLQ sau đúng `STREAM_MAX_RETRY` lần (mặc định 3)
- [ ] XCLAIM reclaim idle entry hoạt động
- [ ] T2-01 → T2-06 pass
- [ ] Control stream `session:{id}:events` emit đủ `stage_started` + `stage_completed`
- [ ] `session:{id}:state` hash cập nhật counter `{stage}_out`

---

*[← P1 — MongoDB](phase-01-tang-du-lieu-mongodb.md) · [P3 — Ingest + Filter →](phase-03-ingest-filter.md)*
