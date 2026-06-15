"""Stage 7 worker — stream LLM tokens, ghi report, emit report_done."""

from __future__ import annotations

import logging
from typing import Any

from src.common.mongo_client import get_db
from src.common.redis_client import get_redis
from src.pipeline._persist import insert_analysis_report, insert_report_chat_message
from src.pipeline._runtime.emit import emit
from src.pipeline._runtime.session_context import coin_matches, get_session_context
from src.pipeline.insight.service import get_insight_pipeline

logger = logging.getLogger(__name__)


async def insight_processor(payload: dict[str, Any], fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage insight:
      1. Nhận scoring_signal từ stage:insight:in
      2. Stream LLM → llm_token events
      3. Ghi analysis_reports + chat_messages type=report
      4. Emit report_done
    """
    session_id = fields.get("session_id", "")
    job_id = fields.get("job_id", "")

    if not session_id:
        logger.warning("Insight skip: missing session_id")
        return []

    redis = await get_redis()
    ctx = await get_session_context(redis, session_id)
    if ctx and not coin_matches(payload.get("coin_id"), ctx["coin_id"]):
        logger.debug(
            "Insight skip %s — session target %s",
            payload.get("coin_id"),
            ctx["coin_id"],
        )
        return []

    pipeline = get_insight_pipeline()
    report, chat_msg = await pipeline.process(payload, session_id=session_id, job_id=job_id)

    if await insert_analysis_report(report) == "skipped":
        logger.debug("Skip duplicate report %s", report.get("report_id"))
        return []

    await insert_report_chat_message(chat_msg)

    db = await get_db()
    await db.analysis_sessions.update_one(
        {"session_id": session_id},
        {"$set": {"report_id": report["report_id"]}},
    )

    redis = await get_redis()
    await emit(
        redis,
        session_id,
        "report_done",
        {"report_id": report["report_id"], "signal_id": report.get("signal_id")},
        job_id=job_id,
    )

    sections = report.get("sections") or {}
    fallback = sections.get("llm_fallback", False)
    logger.info(
        "Insight %s: report %s fallback=%s",
        report.get("coin_id"),
        report.get("report_id"),
        fallback,
    )

    report["_summary"] = {
        "report_id": report.get("report_id"),
        "coin_id": report.get("coin_id"),
        "sections": len([k for k, v in sections.items() if v and k != "llm_fallback"]),
        "llm_fallback": fallback,
    }
    return [report]
