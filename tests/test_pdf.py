"""Kiểm tra PDF export (Phase 7).

Chạy: uv run pytest tests/test_pdf.py -v
Cần: weasyprint (optional dependency export)

Danh sách test:
  test_t7_06_generate_pdf_bytes       — T7-06 generate_pdf trả bytes
  test_t7_07_pdf_content_sections     — T7-07 HTML có header, ETL, signal, report
"""

from __future__ import annotations

import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.api.services.pdf_export import generate_pdf, markdown_to_html, render_pdf_template


@pytest.fixture
async def test_db(monkeypatch: pytest.MonkeyPatch):
    from src.common.mongo_client import close_mongo, get_db

    monkeypatch.setattr("src.common.config.settings.MONGODB_DB", "crypto_mvp_test_pdf")
    await close_mongo()
    try:
        db = await get_db()
        from src.common.schema import bootstrap_indexes

        await bootstrap_indexes(db)
        yield db
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    finally:
        try:
            db = await get_db()
            await db.client.drop_database("crypto_mvp_test_pdf")
        except Exception:
            pass
        await close_mongo()


@pytest.fixture
def sample_data() -> tuple[dict, dict, list, dict]:
    session = {
        "session_id": "sess-pdf-1",
        "coin_id": "BTC",
        "timeframe": "1h",
        "job_id": "job-pdf-1",
        "created_at": datetime(2026, 6, 14, tzinfo=timezone.utc),
    }
    report = {
        "report_id": "rep-1",
        "signal_id": "sig-1",
        "summary": "BTC cho tín hiệu BUY.",
        "sections": {
            "full_text": (
                "# Báo cáo BTC\n\n"
                "Phân tích **BUY** signal.\n\n"
                "## Key findings\n\n"
                "- Giá tăng mạnh\n"
                "- Volume cao\n\n"
                "| Metric | Value |\n"
                "| --- | --- |\n"
                "| Alpha | 68.2 |\n"
            ),
        },
    }
    stages = [
        {"stage": "ingest", "status": "completed", "records_in": 0, "records_out": 10, "duration_ms": 100},
        {"stage": "scoring", "status": "completed", "records_in": 1, "records_out": 1, "duration_ms": 50},
    ]
    signal = {
        "signal_id": "sig-1",
        "action": "BUY",
        "metrics": {"galaxy_alpha_score": 68.2, "galaxy_safety_score": 55.1},
        "execution": {"target_price": 70000, "stop_loss": 65000},
    }
    return session, report, stages, signal


def test_t7_07_pdf_content_sections(sample_data) -> None:
    """T7-07: HTML template có header, ETL table, signal, LLM report."""
    session, report, stages, signal = sample_data
    html_out = render_pdf_template(session, report, stages, signal)

    assert "BTC" in html_out
    assert "sess-pdf-1" in html_out
    assert "ETL Summary" in html_out
    assert "ingest" in html_out
    assert "Signal Card" in html_out
    assert "BUY" in html_out
    assert "LLM Report" in html_out
    assert "<h1>Báo cáo BTC</h1>" in html_out
    assert "<strong>BUY</strong>" in html_out
    assert "<h2>Key findings</h2>" in html_out
    assert "<li>Giá tăng mạnh</li>" in html_out
    assert "<table>" in html_out


def test_markdown_to_html_renders_gfm() -> None:
    """Markdown được convert sang HTML, không chỉ escape + br."""
    md = "## Section\n\n- item one\n- **bold** two"
    out = markdown_to_html(md)
    assert "<h2>Section</h2>" in out
    assert "<ul>" in out
    assert "<strong>bold</strong>" in out


@pytest.mark.asyncio
async def test_t7_06_generate_pdf_bytes(test_db, monkeypatch) -> None:
    """T7-06: generate_pdf trả bytes PDF hợp lệ."""
    pytest.importorskip("weasyprint", reason="weasyprint not installed — uv sync --extra export")
    session_id = f"sess-{uuid.uuid4().hex[:8]}"
    job_id = "job-pdf"
    now = datetime.now(timezone.utc)

    await test_db.analysis_sessions.insert_one({
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "job_id": job_id,
        "status": "completed",
        "created_at": now,
    })
    await test_db.analysis_reports.insert_one({
        "report_id": f"rep-{uuid.uuid4().hex[:8]}",
        "session_id": session_id,
        "coin_id": "BTC",
        "timeframe": "1h",
        "signal_id": "sig-pdf",
        "summary": "BTC BUY signal.",
        "sections": {"full_text": "LLM report content for PDF."},
        "generated_at": now,
    })
    await test_db.pipeline_stage_runs.insert_one({
        "run_id": f"{job_id}:scoring",
        "job_id": job_id,
        "stage": "scoring",
        "status": "completed",
        "records_in": 1,
        "records_out": 1,
        "duration_ms": 10,
    })
    await test_db.scoring_signals.insert_one({
        "signal_id": "sig-pdf",
        "coin_id": "BTC",
        "action": "BUY",
        "timestamp": int(now.timestamp()),
        "metrics": {"galaxy_alpha_score": 70, "galaxy_safety_score": 50},
        "execution": {"target_price": 70000, "stop_loss": 65000},
    })

    pdf_bytes = await generate_pdf(session_id)
    assert isinstance(pdf_bytes, bytes)
    assert len(pdf_bytes) > 100
    assert pdf_bytes[:4] == b"%PDF"
