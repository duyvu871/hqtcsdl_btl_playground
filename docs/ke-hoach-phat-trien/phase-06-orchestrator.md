# P6 — Orchestrator & Session State Machine

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §6 Kiến trúc điều phối · §6.2 Session state machine · §13.3 Orchestrator monitor mã giả  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.4 Module `src/orchestrator/`

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P5 — Influence + Scoring](phase-05-influence-scoring.md) |
| **FR liên quan** | **FR-10** (Orchestrator E2E một lệnh Stage 1→7) · **FR-15** (pipeline_jobs / pipeline_stage_runs) |
| **Điều hướng** | [← P5](phase-05-influence-scoring.md) · [P7 →](phase-07-insight-pdf.md) |

---

## 1. Mục tiêu

Xây dựng **Orchestrator** điều phối toàn bộ pipeline theo session: tạo session → planning → kick-off Stage 1 → monitor control stream → finalize khi Stage 6 xong (chưa Stage 7). Snapshot toàn bộ job metrics từ Redis Hash sang MongoDB.

---

## 2. Công việc & tái sử dụng

### 2.1. Cấu trúc module

```text
src/orchestrator/
├── __init__.py
├── session.py      # Tạo session, init Redis Hash, XADD kickoff
├── planning.py     # Emit 7 planning_step vào control stream + chat_messages
└── monitor.py      # Monitor loop + state machine + finalize
```

### 2.2. `session.py` — Tạo session

```python
async def create_session(coin_id: str, timeframe: str) -> dict:
    session_id = str(uuid4())
    job_id = f"job-{datetime.utcnow():%Y%m%d-%H%M%S}"

    # 1. Insert analysis_sessions MongoDB
    await db.analysis_sessions.insert_one({
        "session_id": session_id, "coin_id": coin_id,
        "timeframe": timeframe, "job_id": job_id,
        "status": "created", "created_at": utcnow(),
    })

    # 2. Init Redis Hash session:{id}:state
    await redis.hset(f"session:{session_id}:state", mapping={
        "status": "created", "coin_id": coin_id,
        "timeframe": timeframe, "job_id": job_id,
        "started_at": utcnow(),
    })

    # 3. Planning phase
    await emit_planning(session_id)

    # 4. Kickoff Stage 1
    await redis.xadd("stage:ingest:in", build_kickoff_entry(
        session_id, job_id, coin_id, timeframe
    ), maxlen=50_000, approximate=True)

    await redis.hset(f"session:{session_id}:state", "status", "running")
    return {"session_id": session_id, "job_id": job_id}
```

### 2.3. `planning.py` — 7 planning steps

```python
PLANNING_STEPS = [
    ("Ingest",     "Thu thập dữ liệu social từ Twitter, Alpha Vantage, Yahoo Finance"),
    ("Filter",     "Lọc spam và nhiễu (cascade L1/L2/L3)"),
    ("NER",        "Nhận diện và gán mã coin từ nội dung"),
    ("Sentiment",  "Phân tích cảm xúc thị trường qua FinBERT"),
    ("Influence",  "Đo trọng số ảnh hưởng và aggregate theo cửa sổ thời gian"),
    ("Scoring",    "Tính Galaxy Alpha/Safety Score và xác định tín hiệu BUY/HOLD"),
    ("Insight",    "Tổng hợp báo cáo phân tích bằng LLM và xuất PDF"),
]

async def emit_planning(session_id: str):
    for i, (stage, desc) in enumerate(PLANNING_STEPS, 1):
        await emit(redis, session_id, "planning_step", {
            "step": i, "stage": stage, "description": desc
        })
        # Mirror vào chat_messages
        await db.chat_messages.insert_one({
            "message_id": str(uuid4()), "session_id": session_id,
            "role": "assistant", "type": "planning",
            "content": f"{i}. {stage} — {desc}",
            "created_at": utcnow(),
        })
```

### 2.4. `monitor.py` — State machine + finalize (từ §13.3)

**State machine (§6.2):**
```
created → planning → running → insight_streaming → completed
                             ↘ failed_partial
```

```python
async def monitor_session(session_id: str, job_id: str):
    stream = f"session:{session_id}:events"
    state_key = f"session:{session_id}:state"
    cursor_key = f"cursor:orch:{session_id}"
    last_id = await redis.get(cursor_key) or "0-0"

    while True:
        entries = await redis.xread({stream: last_id}, block=30_000, count=100)
        for entry_id, fields in entries[0][1]:
            last_id = entry_id
            await redis.set(cursor_key, last_id, ex=7*86400)

            match fields["event_type"]:
                case "stage_completed":
                    stage = json.loads(fields["data"])["stage"]
                    await redis.hset(state_key, "current_stage", stage)
                    if stage == "scoring":
                        await redis.hset(state_key, "status", "insight_streaming")
                case "stage_failed":
                    await redis.hset(state_key, "status", "failed_partial")
                case "report_done":
                    await finalize_session(session_id, job_id)
                    return
                case "signal_ready":
                    data = json.loads(fields["data"])
                    await db.chat_messages.insert_one({
                        "type": "signal_card", "session_id": session_id,
                        "role": "assistant", "metadata": data, ...
                    })
```

### 2.5. `finalize_session()` — Snapshot Redis Hash → MongoDB

```python
async def finalize_session(session_id: str, job_id: str):
    state = await redis.hgetall(f"session:{session_id}:state")

    # Ghi pipeline_jobs
    await db.pipeline_jobs.update_one(
        {"job_id": job_id},
        {"$set": {"status": "completed", "finished_at": utcnow(), **state}},
        upsert=True,
    )

    # Ghi pipeline_stage_runs (mỗi stage 1 doc)
    for stage in STAGE_ORDER:
        await db.pipeline_stage_runs.update_one(
            {"job_id": job_id, "stage": stage},
            {"$set": {
                "records_in":   int(state.get(f"{stage}_in", 0)),
                "records_out":  int(state.get(f"{stage}_out", 0)),
                "duration_ms":  int(state.get(f"{stage}_duration_ms", 0)),
                "status": "completed",
            }},
            upsert=True,
        )

    # Update analysis_sessions
    await db.analysis_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"status": "completed", "finished_at": utcnow()}},
    )

    await emit(redis, session_id, "session_completed", {})
```

### 2.6. Hai consumer độc lập trên control stream (§6.3)

| Consumer | Cơ chế | Mục đích |
|----------|--------|----------|
| **Orchestrator** | `XREAD` cursor lưu `cursor:orch:{id}` Redis KV | State machine, finalize |
| **WS Broadcaster** (P8) | `XREAD` cursor per WebSocket connection | Push UI realtime |

Không dùng consumer group cho control stream vì cả hai cần nhận **mọi** event (broadcast semantics).

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh | Kết quả mong đợi |
|---------|-------|------|------------------|
| T6-01 | Unit: chuyển trạng thái `created → running` | `test_state_machine.py` | `status=running` sau kickoff |
| T6-02 | Unit: `stage_completed scoring` → `insight_streaming` | Mock event | `status=insight_streaming` |
| T6-03 | Unit: `stage_failed` → `failed_partial` | Mock event | `status=failed_partial` |
| T6-04 | Planning: 7 `planning_step` emit | Tạo session | Control stream có 7 entries `event_type=planning_step` |
| T6-05 | Planning: mirror `chat_messages` | Tạo session | MongoDB `chat_messages` có 7 doc `type=planning` |
| T6-06 | Integration E2E Stage 1→6 | `python -m pipeline.orchestrator run --coin BTC --timeframe 1h` | Session `status=insight_streaming`; Stage 1→6 completed |
| T6-07 | Finalize snapshot | Sau Stage 6 | `pipeline_stage_runs` 6 docs với `records_in/out + duration_ms` |

```bash
pytest tests/test_orchestrator.py -v
# Integration (cần docker compose full pipeline)
python -m src.orchestrator.session run --coin BTC --timeframe 1h
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/orchestrator/` có `session.py`, `planning.py`, `monitor.py`
- [ ] 1 lệnh `create_session(coin, timeframe)` chạy hết Stage 1→6 (chưa Stage 7)
- [ ] 7 `planning_step` emit vào control stream + mirror `chat_messages`
- [ ] State machine chuyển đúng: created → planning → running → insight_streaming
- [ ] `stage_failed` → `failed_partial`
- [ ] Finalize ghi `pipeline_jobs` + `pipeline_stage_runs` từ Redis Hash
- [ ] T6-01 → T6-07 pass
- [ ] Hai consumer (Orchestrator + WS sẽ thêm P8) độc lập trên control stream không xung đột

---

*[← P5 — Influence + Scoring](phase-05-influence-scoring.md) · [P7 — LLM Insight + PDF →](phase-07-insight-pdf.md)*
