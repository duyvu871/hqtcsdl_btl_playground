"""Kiểm tra FastAPI REST + WebSocket (Phase 8).

Chạy: uv run pytest tests/test_api.py -v
Cần: docker compose (MongoDB + Redis), uv sync --extra api

Danh sách test:
  test_t8_01_health_check              — T8-01 GET /api/v1/health
  test_t8_02_create_session            — T8-02 POST /api/v1/analysis/sessions
  test_t8_03_session_messages          — T8-03 GET messages
  test_t8_04_pdf_endpoint              — T8-04 export PDF
  test_t8_05_signal_card               — T8-05 GET /coins/BTC/signal
  test_t8_06_ohlcv_datafeed            — T8-06 GET /market/ohlcv
  test_t8_07_ws_catchup                — T8-07 WS catch-up từ last_id=0
  test_t8_08_ws_live                   — T8-08 WS nhận event live
  test_t8_09_ws_reconnect              — T8-09 reconnect với last_id
  test_t8_10_cors_header               — T8-10 CORS localhost:3000
"""

from __future__ import annotations

import json
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest
import redis as sync_redis
from fastapi.testclient import TestClient
from pymongo import MongoClient

from src.api.main import app
from src.common.config import settings
from src.pipeline._runtime.keys import CTL_MAXLEN, ctl_stream

TEST_DB = "crypto_mvp_test_api"


def _mongo() -> MongoClient:
    return MongoClient(settings.MONGODB_URI, serverSelectionTimeoutMS=3000)


def _redis() -> sync_redis.Redis:
    return sync_redis.Redis.from_url(settings.REDIS_URL, decode_responses=True)


def _emit_sync(session_id: str, event_type: str, data: dict) -> str:
    """Emit control event qua sync Redis — tránh xung đột event loop với TestClient."""
    r = _redis()
    entry_id = r.xadd(
        ctl_stream(session_id),
        {
            "event_type": event_type,
            "session_id": session_id,
            "job_id": "",
            "data": json.dumps(data),
            "ts": datetime.now(timezone.utc).isoformat(),
        },
        maxlen=CTL_MAXLEN,
        approximate=True,
    )
    return str(entry_id)


@pytest.fixture(autouse=True)
def reset_async_clients():
    """Reset motor/redis singleton — TestClient tạo loop mới mỗi request."""
    import src.common.mongo_client as mc
    import src.common.redis_client as rc

    mc._client = None
    rc._redis = None
    yield
    mc._client = None
    rc._redis = None


@pytest.fixture
def api_env(monkeypatch: pytest.MonkeyPatch):
    """Seed DB qua sync client; teardown drop database."""
    monkeypatch.setattr("src.common.config.settings.MONGODB_DB", TEST_DB)
    try:
        client = _mongo()
        client.admin.command("ping")
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    try:
        _redis().ping()
    except Exception as exc:
        pytest.skip(f"Redis not available: {exc}")

    db = client[TEST_DB]

    yield db

    client.drop_database(TEST_DB)
    client.close()


@pytest.fixture
def client() -> TestClient:
    return TestClient(app)


def test_t8_01_health_check(client: TestClient) -> None:
    """T8-01: Health check trả mongodb + redis ok."""
    resp = client.get("/api/v1/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["mongodb"] == "ok"
    assert body["redis"] == "ok"


def test_t8_02_create_session(client: TestClient, api_env, monkeypatch) -> None:
    """T8-02: POST /analysis/sessions trả session_id + job_id."""

    def _noop_monitor(*_args, **_kwargs) -> None:
        return

    monkeypatch.setattr("src.api.routes.analysis.spawn_session_monitor", _noop_monitor)

    resp = client.post(
        "/api/v1/analysis/sessions",
        json={"coin_id": "BTC", "timeframe": "1h"},
    )
    assert resp.status_code == 201
    body = resp.json()
    assert "session_id" in body
    assert "job_id" in body

    session = api_env.analysis_sessions.find_one({"session_id": body["session_id"]})
    assert session is not None
    assert session["status"] in ("running", "pending")


def test_t8_03_session_messages(client: TestClient, api_env) -> None:
    """T8-03: GET messages trả chat_messages đúng thứ tự."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    api_env.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "job_id": "job-msg",
        "status": "completed",
        "created_at": now,
    })
    api_env.chat_messages.insert_many([
        {
            "message_id": "m1",
            "session_id": session_id,
            "role": "user",
            "type": "user",
            "content": "Phân tích BTC",
            "metadata": {},
            "created_at": now,
        },
        {
            "message_id": "m2",
            "session_id": session_id,
            "role": "assistant",
            "type": "report",
            "content": "Báo cáo BTC",
            "metadata": {},
            "created_at": datetime.now(timezone.utc),
        },
    ])

    resp = client.get(f"/api/v1/analysis/sessions/{session_id}/messages")
    assert resp.status_code == 200
    messages = resp.json()["messages"]
    assert len(messages) == 2
    assert messages[0]["message_id"] == "m1"
    assert messages[1]["type"] == "report"


def test_t8_04_pdf_endpoint(client: TestClient, api_env) -> None:
    """T8-04: PDF endpoint trả application/pdf."""
    pytest.importorskip("weasyprint", reason="weasyprint not installed")
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    now = datetime.now(timezone.utc)
    api_env.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "job_id": "job-pdf",
        "status": "completed",
        "created_at": now,
    })
    api_env.analysis_reports.insert_one({
        "report_id": f"rep-{uuid.uuid4().hex[:8]}",
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "signal_id": "sig-api",
        "summary": "BTC BUY",
        "sections": {"full_text": "Report body"},
        "generated_at": now,
    })
    api_env.scoring_signals.insert_one({
        "signal_id": "sig-api",
        "coin_id": "BTC",
        "action": "BUY",
        "timestamp": int(now.timestamp()),
        "metrics": {"galaxy_alpha_score": 70, "galaxy_safety_score": 50},
        "execution": {"target_price": 70000, "stop_loss": 65000},
    })

    resp = client.get(f"/api/v1/analysis/sessions/{session_id}/export/pdf")
    assert resp.status_code == 200
    assert resp.headers["content-type"] == "application/pdf"
    assert resp.content[:4] == b"%PDF"


def test_t8_05_signal_card(client: TestClient, api_env) -> None:
    """T8-05: Signal card có action, metrics, execution."""
    now = datetime.now(timezone.utc)
    api_env.scoring_signals.insert_one({
        "signal_id": "sig-btc-1",
        "coin_id": "BTC",
        "action": "BUY",
        "timestamp": int(now.timestamp()),
        "metrics": {"galaxy_alpha_score": 68.2, "galaxy_safety_score": 55.1},
        "execution": {"target_price": 70350.0, "stop_loss": 65660.0},
    })

    resp = client.get("/api/v1/coins/BTC/signal?timeframe=1h")
    assert resp.status_code == 200
    body = resp.json()
    assert body["action"] == "BUY"
    assert "metrics" in body
    assert "execution" in body


def test_t8_06_ohlcv_datafeed(client: TestClient, api_env, monkeypatch) -> None:
    """T8-06: OHLCV trả candles array."""
    now = datetime.now(timezone.utc)
    for ts, close in [(1714000000, 65000.0), (1714003600, 65500.0)]:
        api_env.market_ohlcv.update_one(
            {"coin_id": "BTC", "timeframe": "1h", "timestamp": ts},
            {"$set": {
                "coin_id": "BTC",
                "timeframe": "1h",
                "timestamp": ts,
                "close": close,
                "volume": 100.0,
                "updated_at": now,
            }},
            upsert=True,
        )

    async def _mock_ohlcv(coin_id: str, interval: str, *, limit: int = 48) -> dict:
        from src.api.services import market_service

        rows = await market_service._load_cached_candles(coin_id, interval, limit)
        return {"coin": coin_id.upper(), "interval": interval, "candles": rows}

    monkeypatch.setattr("src.api.routes.market.get_ohlcv", _mock_ohlcv)

    resp = client.get("/api/v1/market/ohlcv?coin=BTC&interval=1h&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert "candles" in body
    assert len(body["candles"]) >= 2
    candle = body["candles"][0]
    assert "time" in candle
    assert "open" in candle
    assert "close" in candle
    assert "volume" in candle


def test_t8_07_ws_catchup(client: TestClient) -> None:
    """T8-07: WS catch-up nhận events từ đầu."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    _emit_sync(session_id, "planning_step", {"step": 1, "title": "Ingest"})
    _emit_sync(session_id, "stage_started", {"stage": "ingest"})

    with client.websocket_connect(f"/ws/analysis/{session_id}?last_id=0") as ws:
        events = [ws.receive_json(), ws.receive_json()]
        types = [e["event_type"] for e in events]
        assert "planning_step" in types
        assert "stage_started" in types


def test_t8_08_ws_live(client: TestClient) -> None:
    """T8-08: WS nhận event emit sau khi connect."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    first_id = _emit_sync(session_id, "stage_started", {"stage": "ingest"})

    with client.websocket_connect(f"/ws/analysis/{session_id}?last_id={first_id}") as ws:
        _emit_sync(session_id, "stage_completed", {"stage": "ingest", "records_out": 1})
        msg = ws.receive_json()
        assert msg["event_type"] == "stage_completed"


def test_t8_09_ws_reconnect(client: TestClient) -> None:
    """T8-09: Reconnect với last_id chỉ nhận events sau đó."""
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    _emit_sync(session_id, "planning_step", {"step": 1})
    id2 = _emit_sync(session_id, "planning_step", {"step": 2})
    _emit_sync(session_id, "planning_step", {"step": 3})

    with client.websocket_connect(f"/ws/analysis/{session_id}?last_id={id2}") as ws:
        msg = ws.receive_json()
        assert msg["event_type"] == "planning_step"
        assert msg["data"]["step"] == 3


def test_t8_10_cors_header(client: TestClient) -> None:
    """T8-10: CORS allow localhost:3000."""
    resp = client.options(
        "/api/v1/health",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "GET",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == "http://localhost:3000"
