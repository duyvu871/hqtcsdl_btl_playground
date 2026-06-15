"""Parse LLM output + build analysis_reports / chat_messages."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from typing import Any


def normalize_report_text(text: str) -> str:
    """Thêm xuống dòng trước các section số để ReactMarkdown render đúng."""
    normalized = re.sub(r"\n?(\d+\.\s)", r"\n\n\1", text.strip())
    normalized = re.sub(r"\n{3,}", "\n\n", normalized)
    return normalized.strip()


def _first_paragraph(text: str) -> str:
    for block in re.split(r"\n\s*\n", text.strip()):
        line = block.strip()
        if line:
            return line[:500]
    return text.strip()[:500] or "Báo cáo phân tích crypto."


def _bullet_lines(text: str, keywords: tuple[str, ...]) -> list[str]:
    findings: list[str] = []
    for line in text.splitlines():
        stripped = line.strip()
        lower = stripped.lower()
        if any(k in lower for k in keywords):
            continue
        if stripped.startswith(("-", "*", "•")):
            item = re.sub(r"^[-*•]\s*", "", stripped).strip()
            if item:
                findings.append(item[:300])
    return findings[:5]


def parse_report_text(full_text: str) -> dict[str, Any]:
    """Trích summary, key_findings, risk_factors, recommendation từ markdown."""
    key_findings = _bullet_lines(full_text, ("risk", "rủi ro", "disclaimer"))
    risk_section = ""
    risk_match = re.search(
        r"(?:risk factors?|rủi ro)[:\s]*\n([\s\S]*?)(?:\n\d+\.|\nrecommendation|\Z)",
        full_text,
        re.IGNORECASE,
    )
    if risk_match:
        risk_section = risk_match.group(1)
    risk_factors = _bullet_lines(risk_section, ()) or key_findings[-3:]

    rec_match = re.search(
        r"(?:recommendation|khuyến nghị)[:\s]*\n?([\s\S]*?)(?:\nDisclaimer|\Z)",
        full_text,
        re.IGNORECASE,
    )
    recommendation = (rec_match.group(1).strip() if rec_match else _first_paragraph(full_text))[:500]

    return {
        "summary": _first_paragraph(full_text),
        "key_findings": key_findings[:5] or ["Không trích xuất được key findings từ LLM."],
        "risk_factors": risk_factors[:3] or ["Biến động thị trường crypto cao."],
        "recommendation": recommendation,
    }


def build_analysis_report(
    *,
    session_id: str,
    signal: dict[str, Any],
    full_text: str,
    llm_model: str,
    llm_fallback: bool,
) -> dict[str, Any]:
    parsed = parse_report_text(full_text)
    metrics = signal.get("metrics") or {}

    return {
        "report_id": str(uuid.uuid4()),
        "session_id": session_id,
        "signal_id": signal.get("signal_id"),
        "coin_id": signal.get("coin_id"),
        "timeframe": signal.get("timeframe"),
        "summary": parsed["summary"],
        "key_findings": parsed["key_findings"],
        "recommendation": parsed["recommendation"],
        "confidence": float(metrics.get("confidence", 0)),
        "model": llm_model,
        "sections": {
            "full_text": full_text,
            "risk_factors": parsed["risk_factors"],
            "llm_fallback": llm_fallback,
            "action": signal.get("action"),
            "metrics": metrics,
            "execution": signal.get("execution") or {},
        },
        "generated_at": datetime.now(timezone.utc),
    }


def build_report_chat_message(
    *,
    session_id: str,
    report: dict[str, Any],
) -> dict[str, Any]:
    full_text = (report.get("sections") or {}).get("full_text") or report.get("summary", "")
    return {
        "message_id": str(uuid.uuid4()),
        "session_id": session_id,
        "role": "assistant",
        "type": "report",
        "content": normalize_report_text(full_text),
        "metadata": {
            "report_id": report["report_id"],
            "signal_id": report.get("signal_id"),
        },
        "created_at": datetime.now(timezone.utc),
    }


def build_fallback_text(signal: dict[str, Any], error: Exception) -> str:
    metrics = signal.get("metrics") or {}
    return (
        f"[LLM unavailable: {error}]\n\n"
        f"Signal: {signal.get('action')} | "
        f"Alpha: {metrics.get('galaxy_alpha_score')} | "
        f"Safety: {metrics.get('galaxy_safety_score')}\n\n"
        "Disclaimer: Không phải lời khuyên đầu tư."
    )
