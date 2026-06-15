"""Stage 6 worker — wire scoring service + emit signal_ready."""

from __future__ import annotations

import logging
from typing import Any

from src.common.redis_client import get_redis
from src.pipeline._persist import insert_scoring_signal
from src.pipeline._runtime.emit import emit
from src.pipeline._runtime.session_context import coin_matches, get_session_context
from src.pipeline.scoring.service import InsufficientCandlesError, get_scoring_pipeline

logger = logging.getLogger(__name__)


async def scoring_processor(payload: dict[str, Any], fields: dict[str, str]) -> list[dict[str, Any]]:
    """
    Processor cho stage scoring:
      1. Nhận batch-trigger từ stage:scoring:in
      2. Join social_history + OHLCV → Galaxy dual-score
      3. Ghi scoring_signals
      4. Emit signal_ready lên control bus
    """
    session_id = fields.get("session_id", "")
    job_id = fields.get("job_id", "")

    if session_id:
        redis = await get_redis()
        ctx = await get_session_context(redis, session_id)
        if ctx:
            if not coin_matches(payload.get("coin_id"), ctx["coin_id"]):
                logger.debug(
                    "Scoring skip %s — session target %s",
                    payload.get("coin_id"),
                    ctx["coin_id"],
                )
                return []
            if not payload.get("timeframe"):
                payload = {**payload, "timeframe": ctx["timeframe"]}

    pipeline = get_scoring_pipeline()
    try:
        signal = await pipeline.score_trigger(payload)
    except InsufficientCandlesError as exc:
        logger.warning("Scoring skip: %s", exc)
        return []

    result = await insert_scoring_signal(signal)
    if result == "skipped":
        logger.debug("Skip duplicate signal %s", signal.get("signal_id"))
        return []

    action = signal["action"]
    alpha = signal["metrics"]["galaxy_alpha_score"]
    safety = signal["metrics"]["galaxy_safety_score"]

    if session_id:
        redis = await get_redis()
        await emit(
            redis,
            session_id,
            "signal_ready",
            {
                "action": action,
                "alpha": alpha,
                "safety": safety,
                "target": signal["execution"]["target_price"],
                "stop": signal["execution"]["stop_loss"],
                "coin_id": signal["coin_id"],
            },
            job_id=job_id,
        )

    logger.info(
        "Scoring %s: %s alpha=%.1f safety=%.1f",
        signal.get("coin_id"),
        action,
        alpha,
        safety,
    )

    signal["_summary"] = {
        "action": action,
        "alpha": alpha,
        "safety": safety,
        "coin_id": signal.get("coin_id"),
    }
    return [signal]
