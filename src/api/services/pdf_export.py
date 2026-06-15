"""PDF export — session header + ETL table + signal + LLM report."""

from __future__ import annotations

import html
from datetime import datetime
from typing import Any

from src.common.mongo_client import get_db
from src.pipeline.insight.documents import normalize_report_text

_REPORT_CSS = """
.report { margin-top: 1.5em; line-height: 1.6; color: #1a1a2e; }
.report h1, .report h2, .report h3, .report h4 {
  color: #1a1a2e;
  font-weight: 700;
  line-height: 1.35;
  margin-top: 1.2em;
  margin-bottom: 0.4em;
  page-break-after: avoid;
}
.report h1 { font-size: 1.35rem; margin-top: 0; }
.report h2 { font-size: 1.15rem; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.2em; }
.report h3 { font-size: 1rem; }
.report h4 { font-size: 0.95rem; color: #334155; }
.report p { margin: 0 0 0.75em; }
.report ul, .report ol { margin: 0 0 0.9em; padding-left: 1.5em; }
.report li { margin-bottom: 0.35em; }
.report strong { font-weight: 600; }
.report blockquote {
  border-left: 3px solid #0ea5e9;
  margin: 0.8em 0;
  padding: 0.4em 0.9em;
  background: #f0f9ff;
  color: #334155;
}
.report hr { border: none; border-top: 1px solid #cbd5e1; margin: 1.2em 0; }
.report code {
  background: #f1f5f9;
  padding: 1px 5px;
  border-radius: 3px;
  font-size: 0.9em;
  font-family: "DejaVu Sans Mono", monospace;
}
.report pre {
  background: #f8fafc;
  border: 1px solid #e2e8f0;
  border-radius: 6px;
  padding: 0.8em;
  overflow-x: auto;
  margin-bottom: 0.9em;
  white-space: pre-wrap;
  word-wrap: break-word;
}
.report pre code { background: none; padding: 0; }
.report a { color: #0369a1; text-decoration: underline; }
.report table { width: 100%; border-collapse: collapse; margin: 0.8em 0; font-size: 0.92em; }
.report th, .report td { border: 1px solid #cbd5e1; padding: 0.45em 0.65em; text-align: left; }
.report th { background: #f1f5f9; font-weight: 600; }
.report tr:nth-child(even) td { background: #f8fafc; }
"""


def markdown_to_html(text: str) -> str:
    """Chuyển markdown báo cáo LLM sang HTML (GFM: tables, fenced code, lists)."""
    import markdown

    normalized = normalize_report_text(text)
    return markdown.markdown(
        normalized,
        extensions=["extra", "sane_lists"],
        output_format="html5",
    )


def render_pdf_template(
    session: dict[str, Any],
    report: dict[str, Any],
    stages: list[dict[str, Any]],
    signal: dict[str, Any] | None,
) -> str:
    """Render HTML cho WeasyPrint."""
    coin = html.escape(str(session.get("coin_id", "")))
    timeframe = html.escape(str(session.get("timeframe", "")))
    session_id = html.escape(str(session.get("session_id", "")))
    created = session.get("created_at")
    if isinstance(created, datetime):
        created_str = created.strftime("%Y-%m-%d %H:%M UTC")
    else:
        created_str = html.escape(str(created or ""))

    stage_rows = ""
    for stage in stages:
        stage_rows += (
            "<tr>"
            f"<td>{html.escape(str(stage.get('stage', '')))}</td>"
            f"<td>{html.escape(str(stage.get('status', '')))}</td>"
            f"<td>{stage.get('records_in', 0)}</td>"
            f"<td>{stage.get('records_out', 0)}</td>"
            f"<td>{stage.get('duration_ms', 0)}</td>"
            "</tr>"
        )

    signal_html = "<p>Không có tín hiệu scoring.</p>"
    if signal:
        metrics = signal.get("metrics") or {}
        execution = signal.get("execution") or {}
        signal_html = (
            "<ul>"
            f"<li><strong>Action:</strong> {html.escape(str(signal.get('action', '')))}</li>"
            f"<li><strong>Alpha:</strong> {metrics.get('galaxy_alpha_score', '—')}</li>"
            f"<li><strong>Safety:</strong> {metrics.get('galaxy_safety_score', '—')}</li>"
            f"<li><strong>Target:</strong> {execution.get('target_price', '—')}</li>"
            f"<li><strong>Stop loss:</strong> {execution.get('stop_loss', '—')}</li>"
            "</ul>"
        )

    sections = report.get("sections") or {}
    raw_text = str(sections.get("full_text") or report.get("summary") or "")
    report_html = markdown_to_html(raw_text) if raw_text.strip() else "<p>Không có nội dung báo cáo.</p>"

    return f"""<!DOCTYPE html>
<html lang="vi">
<head>
  <meta charset="utf-8"/>
  <title>Crypto Analysis Report — {coin}</title>
  <style>
    body {{ font-family: sans-serif; margin: 2cm; font-size: 12px; }}
    h1, h2 {{ color: #1a1a2e; }}
    table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
    th, td {{ border: 1px solid #ccc; padding: 6px 8px; text-align: left; }}
    th {{ background: #f0f0f0; }}
    {_REPORT_CSS}
  </style>
</head>
<body>
  <h1>Báo cáo phân tích Crypto</h1>
  <p><strong>Session:</strong> {session_id}</p>
  <p><strong>Coin:</strong> {coin} &nbsp; <strong>Timeframe:</strong> {timeframe}</p>
  <p><strong>Ngày tạo:</strong> {created_str}</p>

  <h2>ETL Summary</h2>
  <table>
    <thead><tr><th>Stage</th><th>Status</th><th>In</th><th>Out</th><th>Duration (ms)</th></tr></thead>
    <tbody>{stage_rows or '<tr><td colspan="5">Không có dữ liệu</td></tr>'}</tbody>
  </table>

  <h2>Signal Card</h2>
  {signal_html}

  <h2>LLM Report</h2>
  <div class="report">{report_html}</div>
  <p><em>Disclaimer: Không phải lời khuyên đầu tư.</em></p>
</body>
</html>"""


async def generate_pdf(session_id: str) -> bytes:
    """Sinh PDF bytes từ session data trong MongoDB."""
    db = await get_db()
    session = await db.analysis_sessions.find_one({"session_id": session_id})
    if not session:
        raise ValueError(f"Session not found: {session_id}")

    report = await db.analysis_reports.find_one({"session_id": session_id})
    if not report:
        raise ValueError(f"Report not found for session: {session_id}")

    job_id = session.get("job_id")
    stages = []
    if job_id:
        stages = await db.pipeline_stage_runs.find({"job_id": job_id}).sort("stage", 1).to_list(20)

    signal = None
    signal_id = report.get("signal_id")
    if signal_id:
        signal = await db.scoring_signals.find_one({"signal_id": signal_id})

    html_content = render_pdf_template(session, report, stages, signal)

    try:
        from weasyprint import HTML
    except ImportError as exc:
        raise RuntimeError(
            "weasyprint not installed — chạy: uv sync --extra api"
        ) from exc

    pdf_bytes = HTML(string=html_content).write_pdf()
    if pdf_bytes is None:
        raise RuntimeError("Failed to generate PDF")
    return pdf_bytes
