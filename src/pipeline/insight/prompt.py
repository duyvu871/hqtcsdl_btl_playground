"""Load + render prompt template insight_v1.txt."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any

from src.common.config import settings


def _fmt_num(value: Any, *, default: float = 0.0, decimals: int = 2) -> str:
    try:
        n = float(value)
        if not math.isfinite(n):
            return f"{default:.{decimals}f}"
        return f"{n:.{decimals}f}"
    except (TypeError, ValueError):
        return f"{default:.{decimals}f}"


def _format_top_events(events: list[dict[str, Any]]) -> str:
    if not events:
        return "(không có sự kiện gần đây)"
    lines: list[str] = []
    for event in events[:10]:
        label = event.get("sentiment_label", "neutral")
        text = str(event.get("clean_text") or event.get("raw_text") or "")[:140]
        score = event.get("sentiment_score", 0)
        lines.append(f"- [{label} {score:+.2f}] {text}")
    return "\n".join(lines)


def load_prompt_template(path: Path | None = None) -> str:
    template_path = path or settings.insight_prompt_path
    return template_path.read_text(encoding="utf-8")


def render_prompt(context: dict[str, Any], *, template: str | None = None) -> str:
    """Render prompt từ context dict."""
    tpl = template if template is not None else load_prompt_template()
    return tpl.format(
        coin_id=context.get("coin_id", "BTC"),
        timeframe=context.get("timeframe", "1h"),
        alpha=_fmt_num(context.get("alpha")),
        safety=_fmt_num(context.get("safety")),
        action=context.get("action", "HOLD"),
        confidence=_fmt_num(context.get("confidence"), decimals=1),
        social_volume=int(context.get("social_volume") or 0),
        weighted_sentiment=_fmt_num(context.get("weighted_sentiment"), decimals=3),
        top_events=_format_top_events(context.get("top_events") or []),
    )
