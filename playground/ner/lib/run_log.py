"""Ghi log run NER ra file (stdlib logging)."""

from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_LOGGER_NAME = "crypto.ner.run"


def default_log_path() -> Path:
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    return Path("logs") / f"ner_run_{ts}.log"


def default_jsonl_path(log_path: Path) -> Path:
    return log_path.with_suffix(".jsonl")


def setup_run_logger(log_path: Path) -> logging.Logger:
    log_path = log_path.expanduser().resolve()
    log_path.parent.mkdir(parents=True, exist_ok=True)

    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(logging.DEBUG)
    logger.handlers.clear()
    logger.propagate = False

    handler = logging.FileHandler(log_path, encoding="utf-8")
    handler.setFormatter(
        logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    logger.addHandler(handler)
    return logger


def get_run_logger() -> logging.Logger | None:
    logger = logging.getLogger(_LOGGER_NAME)
    return logger if logger.handlers else None


def log_event_record(
    *,
    event: dict[str, Any],
    outcome: Any,
    docs: list[dict[str, Any]],
    jsonl_path: Path | None = None,
) -> None:
    logger = get_run_logger()
    text = str(event.get("clean_text") or event.get("raw_text") or "")
    if len(text) > 300:
        text_preview = text[:300] + "..."
    else:
        text_preview = text

    mentions = [
        {
            "coin_id": m.coin_id,
            "method": m.method,
            "evidence": m.evidence,
            "confidence": m.confidence,
        }
        for m in outcome.mentions
    ]

    record = {
        "parent_event_id": event.get("event_id"),
        "source": event.get("source"),
        "author_id": event.get("author_id"),
        "mode": outcome.mode,
        "notes": outcome.notes,
        "used_llm": outcome.used_llm,
        "llm_error": outcome.llm_error,
        "mentions": mentions,
        "fanout_coin_ids": [d.get("coin_id") for d in docs],
        "text_preview": text_preview,
    }

    if logger:
        parts = [
            f"event={record['parent_event_id']}",
            f"source={record['source']}",
            f"notes={record['notes']}",
            f"coins={record['fanout_coin_ids']}",
        ]
        if outcome.llm_error:
            parts.append(f"llm_error={outcome.llm_error}")
        logger.info(" | ".join(parts))
        if outcome.llm_error:
            logger.error("LLM error for %s: %s", record["parent_event_id"], outcome.llm_error)
        if not mentions:
            logger.warning("No mentions: %s | %s", record["parent_event_id"], text_preview[:120])

    if jsonl_path is not None:
        jsonl_path.parent.mkdir(parents=True, exist_ok=True)
        with jsonl_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def log_summary(logger: logging.Logger, *, stats: Any, mode: str, model: str | None, log_path: Path) -> None:
    logger.info("=== SUMMARY ===")
    logger.info("log_file=%s", log_path)
    logger.info("mode=%s model=%s", mode, model or "none")
    logger.info("total=%s with_mentions=%s without_mentions=%s fanout=%s",
                stats.total, stats.with_mentions, stats.without_mentions, stats.fanout_records)
    logger.info("llm_calls=%s llm_errors=%s", stats.llm_calls, stats.llm_errors)
    if stats.by_method:
        for key in sorted(stats.by_method):
            logger.info("method.%s=%s", key, stats.by_method[key])
