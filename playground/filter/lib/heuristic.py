"""L1 — heuristic spam/noise rules (CPU, <0.1ms/event)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

_PUMP_PATTERNS = re.compile(
    r"(?i)"
    r"(\b100x\b|\b1000x\b|to the moon|moonshot|guaranteed profit|"
    r"free airdrop|claim your|join (our|my) telegram|t\.me/|"
    r"dm me for|send \d+ (btc|eth)|double your|"
    r"not financial advice.{0,20}buy now|"
    r"presale ends|ido on|whitelist spot)",
)

_MIN_TEXT_LEN = 3


@dataclass(frozen=True)
class HeuristicConfig:
    min_likes: int = 0
    min_text_len: int = _MIN_TEXT_LEN
    max_per_author: int = 0  # 0 = tắt cap trong batch
    min_engagement_ratio: float = 0.0  # 0 = tắt
    max_engagement_ratio: float = 0.0  # 0 = tắt; >0 flag shill bất thường
    skip_news: bool = True


@dataclass(frozen=True)
class HeuristicResult:
    passed: bool
    reason: str | None = None
    clean_text: str = ""


def normalize_text(text: str) -> str:
    return " ".join(str(text or "").split())


def _engagement(metrics: dict[str, Any]) -> int:
    likes = int(metrics.get("likes") or 0)
    retweets = int(metrics.get("retweets") or metrics.get("shares") or 0)
    comments = int(metrics.get("comments") or 0)
    return likes + retweets + comments


def check_heuristic(
    event: dict[str, Any],
    *,
    config: HeuristicConfig,
    author_counts: dict[str, int] | None = None,
) -> HeuristicResult:
    source = str(event.get("source") or "")
    if config.skip_news and source == "news":
        text = normalize_text(str(event.get("raw_text") or ""))
        if len(text) < config.min_text_len:
            return HeuristicResult(False, "empty_text", text)
        return HeuristicResult(True, clean_text=text)

    text = normalize_text(str(event.get("raw_text") or ""))
    if len(text) < config.min_text_len:
        return HeuristicResult(False, "empty_text", text)

    metrics = event.get("metrics") or {}
    likes = int(metrics.get("likes") or 0)
    if likes < config.min_likes:
        return HeuristicResult(False, "min_likes", text)

    author = str(event.get("author_id") or "unknown")
    if config.max_per_author > 0 and author_counts is not None:
        n = author_counts.get(author, 0)
        if n >= config.max_per_author:
            return HeuristicResult(False, "max_per_author", text)

    followers = metrics.get("followers")
    if followers and int(followers) > 0:
        ratio = _engagement(metrics) / int(followers)
        if config.min_engagement_ratio > 0 and ratio < config.min_engagement_ratio:
            return HeuristicResult(False, "low_engagement_ratio", text)
        if config.max_engagement_ratio > 0 and ratio > config.max_engagement_ratio:
            return HeuristicResult(False, "high_engagement_ratio", text)

    if _PUMP_PATTERNS.search(text):
        return HeuristicResult(False, "pump_regex", text)

    return HeuristicResult(True, clean_text=text)
