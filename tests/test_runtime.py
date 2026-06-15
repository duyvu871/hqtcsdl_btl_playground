"""Kiểm tra Redis Streams runtime (Phase 2) — worker harness.

Chạy: uv run pytest tests/test_runtime.py -v
Cần: Redis (docker compose).

Danh sách test:
  test_echo_stage       — đọc 1 message, xử lý, ack, đẩy xuống stream tiếp
  test_fanout           — 1 input → processor trả 3 doc → 3 message downstream
  test_dlq_after_max_retry — lỗi 3 lần → message vào DLQ (dead-letter)
  test_reclaim_pending  — worker crash → worker khác nhận lại message treo
  test_state_counters   — đếm số output vào session:{id}:state
  test_control_events   — ghi stage_started / stage_completed vào control bus
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

# python tests/test_runtime.py
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.common.redis_client import close_redis, get_redis
from src.pipeline._runtime.keys import ctl_stream, dlq_stream, group, in_stream, state_key
from src.pipeline._runtime.worker import (
    ensure_consumer_group,
    pending_count,
    process_batch,
    publish_entry,
    reclaim_pending,
)

ECHO_STAGE = "echo"
ECHO_DOWNSTREAM = "stage:echo:out"
TEST_STAGE = "test"


async def _cleanup_streams(redis, *stages: str) -> None:
    """Xóa stream test sau mỗi test case."""
    keys: list[str] = []
    for stage in stages:
        keys.extend([in_stream(stage), dlq_stream(stage), f"stage:{stage}:out"])
    keys.append(in_stream(ECHO_STAGE))
    keys.append(ECHO_DOWNSTREAM)
    if keys:
        await redis.delete(*keys)


async def _cleanup_session(redis, session_id: str) -> None:
    await redis.delete(ctl_stream(session_id), state_key(session_id))


@pytest.fixture
async def redis_client():
    try:
        redis = await get_redis()
        yield redis
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")
    finally:
        await close_redis()


@pytest.fixture
async def echo_env(redis_client):
    """Stream echo sạch trước/sau test."""
    await _cleanup_streams(redis_client, ECHO_STAGE)
    yield redis_client
    await _cleanup_streams(redis_client, ECHO_STAGE)


@pytest.fixture
async def test_env(redis_client):
    """Stream test (DLQ) sạch trước/sau test."""
    await _cleanup_streams(redis_client, TEST_STAGE)
    yield redis_client
    await _cleanup_streams(redis_client, TEST_STAGE)


# ── T2-01: echo publish → consume → ack ─────────────────────────────────────
@pytest.mark.asyncio
async def test_echo_stage(echo_env) -> None:
    """Gửi 1 message → worker xử lý → ack → có 1 entry ở stream downstream."""
    redis = echo_env
    session_id = "sess-t2-01"

    await publish_entry(
        redis,
        ECHO_STAGE,
        {"msg": "hello"},
        session_id=session_id,
        job_id="job-01",
        trace_id="trace-01",
    )

    async def echo_processor(payload: dict, _fields: dict) -> dict:
        return {"echo": payload["msg"]}

    processed = await process_batch(
        redis,
        ECHO_STAGE,
        echo_processor,
        consumer="echo-worker",
        downstream=ECHO_DOWNSTREAM,
        block_ms=1000,
    )
    assert processed == 1
    assert await pending_count(redis, ECHO_STAGE) == 0

    downstream_len = await redis.xlen(ECHO_DOWNSTREAM)
    assert downstream_len == 1


# ── T2-02: fan-out 1 input → 3 downstream ──────────────────────────────────
@pytest.mark.asyncio
async def test_fanout(echo_env) -> None:
    """Processor trả list 3 item → stream downstream có đúng 3 message."""
    redis = echo_env
    session_id = "sess-t2-02"

    await publish_entry(
        redis,
        ECHO_STAGE,
        {"coins": ["BTC", "ETH", "SOL"]},
        session_id=session_id,
        job_id="job-02",
        trace_id="trace-02",
    )

    async def fanout_processor(payload: dict, _fields: dict) -> list[dict]:
        return [{"coin": c} for c in payload["coins"]]

    await process_batch(
        redis,
        ECHO_STAGE,
        fanout_processor,
        consumer="fanout-worker",
        downstream=ECHO_DOWNSTREAM,
        block_ms=1000,
    )

    assert await redis.xlen(ECHO_DOWNSTREAM) == 3


# ── T2-03: DLQ sau max retry ─────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_dlq_after_max_retry(test_env, monkeypatch) -> None:
    """Processor luôn lỗi → sau 3 lần retry message chuyển sang DLQ."""
    redis = test_env
    monkeypatch.setattr("src.common.config.settings.STREAM_MAX_RETRY", 3)
    session_id = "sess-t2-03"

    entry_id = await publish_entry(
        redis,
        TEST_STAGE,
        {"fail": True},
        session_id=session_id,
        job_id="job-03",
        trace_id="trace-03",
    )

    async def fail_processor(_payload: dict, _fields: dict) -> dict:
        raise RuntimeError("simulated failure")

    # Lần 1: đọc entry mới; lần 2-3: reclaim từ PEL (process_batch chỉ đọc ">")
    await process_batch(
        redis,
        TEST_STAGE,
        fail_processor,
        consumer="fail-w1",
        block_ms=500,
    )
    for consumer in ("fail-w2", "fail-w3"):
        await reclaim_pending(
            redis,
            TEST_STAGE,
            fail_processor,
            consumer=consumer,
            min_idle_ms=0,
        )

    assert await redis.xlen(dlq_stream(TEST_STAGE)) == 1
    assert await pending_count(redis, TEST_STAGE) == 0

    dlq_entries = await redis.xrange(dlq_stream(TEST_STAGE))
    assert dlq_entries[0][0]  # có entry
    assert "error" in dlq_entries[0][1]


# ── T2-04: XAUTOCLAIM reclaim entry treo ─────────────────────────────────────
@pytest.mark.asyncio
async def test_reclaim_pending(echo_env) -> None:
    """Worker 1 đọc nhưng không ack → worker 2 reclaim và xử lý xong."""
    redis = echo_env
    session_id = "sess-t2-04"
    stream = in_stream(ECHO_STAGE)
    grp = group(ECHO_STAGE)

    await publish_entry(
        redis,
        ECHO_STAGE,
        {"msg": "reclaim-me"},
        session_id=session_id,
        job_id="job-04",
        trace_id="trace-04",
    )
    await ensure_consumer_group(redis, ECHO_STAGE)

    # Worker-1 đọc nhưng không ack — giả lập crash
    batches = await redis.xreadgroup(grp, "worker-1", {stream: ">"}, count=1, block=1000)
    assert batches
    entry_id = batches[0][1][0][0]
    assert await pending_count(redis, ECHO_STAGE) == 1

    results: list[dict] = []

    async def reclaim_processor(payload: dict, _fields: dict) -> dict:
        results.append(payload)
        return {"echo": payload["msg"]}

    # Worker-2 reclaim entry idle (min_idle=0 cho test)
    claimed = await reclaim_pending(
        redis,
        ECHO_STAGE,
        reclaim_processor,
        consumer="worker-2",
        downstream=ECHO_DOWNSTREAM,
        min_idle_ms=0,
    )
    assert claimed == 1
    assert results == [{"msg": "reclaim-me"}]
    assert await pending_count(redis, ECHO_STAGE) == 0
    assert await redis.xlen(ECHO_DOWNSTREAM) == 1


# ── T2-05: Hash counters ─────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_state_counters(echo_env) -> None:
    """Sau xử lý, hash session:{id}:state ghi đúng số output."""
    redis = echo_env
    session_id = "sess-t2-05"

    await publish_entry(
        redis,
        ECHO_STAGE,
        {"n": 2},
        session_id=session_id,
        job_id="job-05",
        trace_id="trace-05",
    )

    async def multi_processor(_payload: dict, _fields: dict) -> list[dict]:
        return [{"i": 1}, {"i": 2}]

    await process_batch(
        redis,
        ECHO_STAGE,
        multi_processor,
        consumer="counter-worker",
        downstream=ECHO_DOWNSTREAM,
        block_ms=1000,
    )

    state = await redis.hgetall(state_key(session_id))
    assert state.get("echo_out") == "2"

    await _cleanup_session(redis, session_id)


# ── T2-06: Control events ────────────────────────────────────────────────────
@pytest.mark.asyncio
async def test_control_events(echo_env) -> None:
    """Control bus ghi stage_started và stage_completed khi worker chạy xong."""
    redis = echo_env
    session_id = "sess-t2-06"

    await publish_entry(
        redis,
        ECHO_STAGE,
        {"msg": "events"},
        session_id=session_id,
        job_id="job-06",
        trace_id="trace-06",
    )

    async def echo_processor(payload: dict, _fields: dict) -> dict:
        return payload

    await process_batch(
        redis,
        ECHO_STAGE,
        echo_processor,
        consumer="events-worker",
        downstream=ECHO_DOWNSTREAM,
        block_ms=1000,
    )

    entries = await redis.xrange(ctl_stream(session_id))
    event_types = [fields["event_type"] for _id, fields in entries]
    assert "stage_started" in event_types
    assert "stage_completed" in event_types

    await _cleanup_session(redis, session_id)


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
