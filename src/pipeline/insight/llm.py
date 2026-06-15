"""OpenRouter streaming LLM cho Stage 7 insight."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from typing import Any

import redis.asyncio as aioredis

from src.common.config import settings
from src.pipeline._runtime.emit import emit

logger = logging.getLogger(__name__)


async def stream_insight_tokens(
    prompt: str,
    *,
    redis: aioredis.Redis,
    session_id: str,
    job_id: str = "",
    model: str | None = None,
) -> AsyncIterator[str]:
    """
    Yield token strings; emit llm_token vào control bus ngay khi nhận.
    Raise nếu thiếu API key hoặc OpenAI client lỗi.
    """
    if not settings.OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY not configured")

    from openai import AsyncOpenAI

    client = AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    )
    resolved_model = model or settings.OPENROUTER_INSIGHT_MODEL

    stream = await client.chat.completions.create(
        model=resolved_model,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    )

    async for chunk in stream:
        token = ""
        if chunk.choices:
            delta = chunk.choices[0].delta
            token = getattr(delta, "content", None) or ""
        if token:
            await emit(redis, session_id, "llm_token", {"token": token}, job_id=job_id)
            yield token


async def collect_insight_text(
    prompt: str,
    *,
    redis: aioredis.Redis,
    session_id: str,
    job_id: str = "",
    model: str | None = None,
) -> tuple[str, str]:
    """Stream + gom full text. Trả (full_text, model_name)."""
    parts: list[str] = []
    resolved_model = model or settings.OPENROUTER_INSIGHT_MODEL
    async for token in stream_insight_tokens(
        prompt,
        redis=redis,
        session_id=session_id,
        job_id=job_id,
        model=resolved_model,
    ):
        parts.append(token)
    return "".join(parts), resolved_model
