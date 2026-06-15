"""Map clean_event + NER outcome → mapped_events documents (fan-out)."""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any

from src.pipeline.ner.pipeline import NerOutcome
from src.pipeline.ner.rules import Mention

_PASSTHROUGH_KEYS = (
    "external_id",
    "tweet_id",
    "link_meta",
    "language",
    "news_provider",
    "related_tickers",
    "subreddit",
    "extra",
    "filter",
    "author_id",
    "metrics",
)


def _now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def build_mapped_docs(
    clean_event: dict[str, Any],
    mentions: list[Mention],
    outcome: NerOutcome,
) -> list[dict[str, Any]]:
    """1 mention = 1 mapped_event — fan-out cho Stage 4 Sentiment."""
    parent_id = clean_event.get("event_id")
    clean_text = str(clean_event.get("clean_text") or clean_event.get("raw_text") or "")
    docs: list[dict[str, Any]] = []

    for mention in mentions:
        doc: dict[str, Any] = {
            "mapped_id": str(uuid.uuid4()),
            "parent_event_id": parent_id,
            "event_id": parent_id,
            "coin_id": mention.coin_id,
            "source": clean_event.get("source"),
            "clean_text": clean_text,
            "author_id": clean_event.get("author_id", "unknown"),
            "metrics": clean_event.get("metrics") or {},
            "timestamp": clean_event.get("timestamp"),
            "is_spam": clean_event.get("is_spam", False),
            "ner_method": mention.method,
            "mentions": [mention.coin_id],
            "ner": {
                "mode": outcome.mode,
                "method": mention.method,
                "evidence": mention.evidence,
                "confidence": mention.confidence,
                "used_llm": outcome.used_llm,
                "notes": outcome.notes,
                "llm_error": outcome.llm_error,
            },
            "mapped_at": _now_ts(),
        }
        for key in _PASSTHROUGH_KEYS:
            if key in clean_event:
                doc[key] = clean_event[key]
        docs.append(doc)

    return docs
