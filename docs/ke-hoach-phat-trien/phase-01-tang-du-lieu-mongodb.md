# P1 — Tầng dữ liệu MongoDB (trọng tâm CSDL)

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §8 Kiến trúc lưu trữ  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.2 Thiết kế cơ sở dữ liệu · ERD [`diagrams/khung-bao-cao/05-erd-mongodb.png`](../diagrams/khung-bao-cao/05-erd-mongodb.png)

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P0 — Nền tảng](phase-00-nen-tang-infra.md) |
| **FR liên quan** | Nền tảng lưu trữ cho FR-01..FR-15; đặc biệt FR-02 (dropped_events), FR-13 (chat_messages) |
| **Điều hướng** | [← P0](phase-00-nen-tang-infra.md) · [P2 →](phase-02-runtime-redis-streams.md) |

---

## 1. Mục tiêu

Tạo đầy đủ **14 collection** với index + ràng buộc theo §3.3.2 bằng script bootstrap **idempotent** (chạy nhiều lần không lỗi). Đây là tầng source-of-truth cho toàn bộ pipeline — mọi stage đọc/ghi MongoDB sau khi xử lý.

---

## 2. Công việc & tái sử dụng

### 2.1. Module schema

**`src/common/schema/__init__.py`** — export `bootstrap_indexes(db)` và các hằng tên collection:

```python
# src/common/schema/__init__.py
COLLECTIONS = [
    "raw_events", "clean_events", "dropped_events",
    "mapped_events", "sentiment_events", "sentiment_aggregates",
    "weighted_events", "influence_aggregates", "scoring_signals",
    "analysis_reports", "analysis_sessions", "chat_messages",
    "pipeline_jobs", "pipeline_stage_runs",
]
```

### 2.2. Bảng collection + index đầy đủ

| Collection | Stage ghi | Index | Loại index |
|------------|-----------|-------|------------|
| `raw_events` | Stage 1 | `(source, external_id)` | Unique sparse |
| `raw_events` | Stage 1 | `timestamp` | Single (sort) |
| `clean_events` | Stage 2 | `event_id` | Unique |
| `clean_events` | Stage 2 | `timestamp` | Single |
| `dropped_events` | Stage 2 | `event_id` | Single |
| `dropped_events` | Stage 2 | `drop_stage` | Single |
| `mapped_events` | Stage 3 | `(parent_event_id, coin_id)` | Unique |
| `mapped_events` | Stage 3 | `coin_id` | Single |
| `sentiment_events` | Stage 4 | `(mapped_id, coin_id)` | Unique |
| `sentiment_events` | Stage 4 | `(coin_id, timestamp)` | Compound |
| `sentiment_aggregates` | Stage 4 | `(coin_id, window_start)` | Compound |
| `weighted_events` | Stage 5 | `source_event_key` | Unique |
| `influence_aggregates` | Stage 5 | `(coin_id, timeframe, window_start)` | Unique |
| `scoring_signals` | Stage 6 | `signal_id` | Unique |
| `scoring_signals` | Stage 6 | `(coin_id, timestamp)` | Compound (DESC) |
| `analysis_reports` | Stage 7 | `(session_id)` | Single |
| `analysis_reports` | Stage 7 | `(coin_id, generated_at)` | Compound (DESC) |
| `analysis_sessions` | API/Orch | `(created_at)` | Single (DESC) |
| `analysis_sessions` | API/Orch | `job_id` | Single |
| `chat_messages` | Orch/WS | `(session_id, created_at)` | Compound (ASC) |
| `pipeline_jobs` | Orchestrator | `session_id` | Single |
| `pipeline_jobs` | Orchestrator | `(status, started_at)` | Compound (DESC) |
| `pipeline_stage_runs` | Orchestrator | `(job_id, stage)` | Compound |

### 2.3. Script bootstrap

**`src/common/schema/bootstrap.py`**:
```python
async def bootstrap_indexes(db):
    """Idempotent — safe to call multiple times."""
    await db.raw_events.create_index(
        [("source", 1), ("external_id", 1)],
        unique=True, sparse=True, name="uq_source_extid"
    )
    await db.mapped_events.create_index(
        [("parent_event_id", 1), ("coin_id", 1)],
        unique=True, name="uq_parent_coin"
    )
    await db.influence_aggregates.create_index(
        [("coin_id", 1), ("timeframe", 1), ("window_start", 1)],
        unique=True, name="uq_agg_window"
    )
    # ... (tất cả index theo bảng trên)
```

**`scripts/bootstrap_db.py`** — entry point CLI:
```bash
python scripts/bootstrap_db.py
# Output: "Bootstrap complete — N indexes created"
```

### 2.4. Data contract trích yếu (tham chiếu §3.3.2)

```
Stage 1 → raw_events:       event_id, source, external_id, raw_text, metrics, timestamp
Stage 2 → clean_events:     + clean_text, filter.stage, filter.layers, filter.fasttext
Stage 2 → dropped_events:   drop_stage, drop_reason, filter
Stage 3 → mapped_events:    mapped_id, parent_event_id, coin_id, ner.method, ner.confidence
Stage 4 → sentiment_events: sentiment_id, sentiment_score, sentiment_label, probabilities
Stage 5 → influence_aggregates: coin_id, timeframe, window_start, sentiment_score, social_volume
Stage 6 → scoring_signals:  signal_id, action, metrics.galaxy_alpha_score, execution
Stage 7 → analysis_reports: report_id, session_id, signal_id, summary, key_findings
Chat   → analysis_sessions: session_id, coin_id, timeframe, job_id, status
Chat   → chat_messages:     message_id, session_id, role, type, content, metadata
Orch   → pipeline_jobs:     job_id, session_id, status, stages[]
Orch   → pipeline_stage_runs: stage, status, records_in, records_out, duration_ms
```

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh chạy | Kết quả mong đợi |
|---------|-------|-----------|------------------|
| T1-01 | Bootstrap idempotent | `python scripts/bootstrap_db.py` × 2 lần | Không lỗi lần 2; không tạo thêm index trùng |
| T1-02 | Unique index raw_events dedup | Insert 2 doc cùng `(source, external_id)` | Lần 2 raise `DuplicateKeyError` |
| T1-03 | Unique index mapped_events fan-out | Insert 2 doc cùng `(parent_event_id, coin_id)` | Raise `DuplicateKeyError` |
| T1-04 | Unique aggregate window | Insert 2 `influence_aggregates` cùng `(coin_id, timeframe, window_start)` | Upsert thành công (không tạo thêm doc) |
| T1-05 | Query plan dùng index | `explain()` trên `chat_messages` filter `session_id` | `winningPlan` dùng index `session_id` |
| T1-06 | Tất cả 14 collection tồn tại | List collection names | 14 tên đúng |

```bash
# Chạy tất cả test P1
pytest tests/test_schema.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] Đủ 14 collection sau bootstrap
- [ ] Tất cả unique index theo bảng §2.2 được tạo
- [ ] Bootstrap chạy 2 lần không lỗi (idempotent)
- [ ] T1-01 → T1-06 pass
- [ ] ERD trong [`05-erd-mongodb.png`](../diagrams/khung-bao-cao/05-erd-mongodb.png) khớp với collection + field chính
- [ ] TC-09 (dedup raw_events) pass ở mức index (xác nhận `DuplicateKeyError`)
- [ ] `explain()` xác nhận index được sử dụng cho query `(session_id, created_at)` trên `chat_messages`

---

*[← P0 — Nền tảng](phase-00-nen-tang-infra.md) · [P2 — Redis Streams Runtime →](phase-02-runtime-redis-streams.md)*
