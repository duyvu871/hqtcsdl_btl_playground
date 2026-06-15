"""Stage 7 business logic — LLM insight report generation."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Any

from src.common.config import settings
from src.common.redis_client import get_redis
from src.pipeline.insight.context import load_insight_context
from src.pipeline.insight.documents import (
    build_analysis_report,
    build_fallback_text,
    build_report_chat_message,
)
from src.pipeline.insight.llm import collect_insight_text
from src.pipeline.insight.prompt import render_prompt

logger = logging.getLogger(__name__)


@dataclass
class InsightPipeline:
    """Build prompt → stream LLM → analysis_reports."""

    async def process(
        self,
        signal: dict[str, Any],
        *,
        session_id: str,
        job_id: str = "",
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Trả (analysis_report, chat_message)."""
        context = await load_insight_context(signal)
        prompt = render_prompt(context)

        redis = await get_redis()
        llm_fallback = False
        llm_model = settings.OPENROUTER_INSIGHT_MODEL

        try:
            full_text, llm_model = await collect_insight_text(
                prompt,
                redis=redis,
                session_id=session_id,
                job_id=job_id,
            )
        except Exception as exc:
            logger.warning("LLM insight fallback: %s", exc)
            full_text = build_fallback_text(signal, exc)
            llm_fallback = True

        report = build_analysis_report(
            session_id=session_id,
            signal=signal,
            full_text=full_text,
            llm_model=llm_model,
            llm_fallback=llm_fallback,
        )
        chat_msg = build_report_chat_message(session_id=session_id, report=report)
        return report, chat_msg


_pipeline: InsightPipeline | None = None


def get_insight_pipeline() -> InsightPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = InsightPipeline()
    return _pipeline


def reset_insight_pipeline() -> None:
    global _pipeline
    _pipeline = None
