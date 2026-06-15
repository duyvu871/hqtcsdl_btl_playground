"""Map raw event + filter outcome → clean/dropped MongoDB documents.

clean_events  → input cho Stage 3 NER (stage:ner:in)
dropped_events → audit trail FR-02 (drop_stage, drop_reason)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from src.pipeline.filter.cascade import FilterOutcome

# Field từ raw_events giữ nguyên sang clean_events (không qua filter)
_PASSTHROUGH_KEYS = (
    "external_id",
    "tweet_id",
    "link_meta",
    "language",
    "ingested_at",
    "news_provider",
    "subreddit",
    "reddit_fetch_mode",
    "related_tickers",
)


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def build_clean_doc(raw: dict[str, Any], outcome: FilterOutcome) -> dict[str, Any]:
    """PASS → clean_events document."""
    doc: dict[str, Any] = {
        "event_id": raw["event_id"],
        "source": raw.get("source"),
        "raw_text": raw.get("raw_text", ""),
        "clean_text": outcome.clean_text,
        "author_id": raw.get("author_id", "unknown"),
        "metrics": raw.get("metrics") or {},
        "timestamp": raw.get("timestamp"),
        "is_spam": False,
        "filter": outcome.meta,
        "filtered_at": _now_ts(),
    }
    for key in _PASSTHROUGH_KEYS:
        if key in raw:
            doc[key] = raw[key]
    return doc


def build_dropped_doc(raw: dict[str, Any], outcome: FilterOutcome) -> dict[str, Any]:
    """DROP → dropped_events audit document."""
    return {
        "event_id": raw.get("event_id"),
        "source": raw.get("source"),
        "raw_text": raw.get("raw_text", ""),
        "author_id": raw.get("author_id"),
        "timestamp": raw.get("timestamp"),
        "drop_reason": outcome.reason,
        "drop_stage": outcome.stage,
        "filter": outcome.meta,
        "dropped_at": _now_ts(),
    }
