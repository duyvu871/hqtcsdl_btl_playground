"""MongoDB $jsonSchema validators for pipeline collections.

Lớp validation thứ nhất (DB-level): MongoDB tự reject document không hợp lệ
khi insert/update (WriteError code 121). Bổ sung cho Pydantic models ở models.py.

Tham chiếu: docs/ke-hoach-phat-trien/phase-01-tang-du-lieu-mongodb.md §2.4
"""

from __future__ import annotations

from typing import Any

# Alias BSON — pipeline dùng cả unix int lẫn ISODate cho timestamp
_STR = {"bsonType": "string"}
_INT = {"bsonType": ["int", "long"]}
_FLOAT = {"bsonType": ["double", "int", "long"]}
_BOOL = {"bsonType": "bool"}
_DATE = {"bsonType": "date"}
_OBJ = {"bsonType": "object"}
_ARR = {"bsonType": "array"}
_TS = {"bsonType": ["int", "long", "date"]}  # unix int or ISODate


def _schema(required: list[str], properties: dict[str, Any]) -> dict[str, Any]:
    """Tạo $jsonSchema validator; additionalProperties=True để stage sau thêm field mới."""
    return {
        "$jsonSchema": {
            "bsonType": "object",
            "required": required,
            "properties": properties,
            "additionalProperties": True,
        }
    }


# ── Stage 1: Ingest ──────────────────────────────────────────────────────────
RAW_EVENTS_VALIDATOR = _schema(
    required=["event_id", "source", "raw_text", "timestamp"],
    properties={
        "event_id": _STR,
        "source": {"bsonType": "string", "enum": ["reddit", "twitter", "telegram", "news"]},
        "external_id": _STR,
        "raw_text": {"bsonType": "string", "minLength": 1},
        "metrics": _OBJ,
        "timestamp": _TS,
        "author_id": _STR,
        "ingested_at": _TS,
        "language": _STR,
    },
)

# ── Stage 2: Filter ──────────────────────────────────────────────────────────
CLEAN_EVENTS_VALIDATOR = _schema(
    required=["event_id", "clean_text", "timestamp"],
    properties={
        "event_id": _STR,
        "parent_event_id": _STR,
        "clean_id": _STR,
        "source": _STR,
        "clean_text": {"bsonType": "string", "minLength": 1},
        "filter": _OBJ,
        "is_spam": _BOOL,
        "timestamp": _TS,
        "author_id": _STR,
        "metrics": _OBJ,
        "filter_passed_at": _DATE,
        "filter_stages": _ARR,
    },
)

DROPPED_EVENTS_VALIDATOR = _schema(
    # Audit trail: lưu event bị loại ở L1/L2/L3 để debug và báo cáo FR-02
    required=["event_id", "drop_stage", "drop_reason"],
    properties={
        "event_id": _STR,
        "drop_stage": _STR,
        "drop_reason": _STR,
        "filter": _OBJ,
        "timestamp": _TS,
        "source": _STR,
        "raw_text": _STR,
    },
)

# ── Stage 3: NER / coin mapping ──────────────────────────────────────────────
MAPPED_EVENTS_VALIDATOR = _schema(
    required=["mapped_id", "parent_event_id", "coin_id"],
    properties={
        "mapped_id": _STR,
        "parent_event_id": _STR,
        "event_id": _STR,
        "coin_id": _STR,
        "source": _STR,
        "clean_text": _STR,
        "ner": _OBJ,
        "ner_method": _STR,
        "mentions": _ARR,
        "timestamp": _TS,
    },
)

# ── Stage 4: Sentiment ───────────────────────────────────────────────────────
SENTIMENT_EVENTS_VALIDATOR = _schema(
    required=["sentiment_id", "mapped_id", "coin_id", "sentiment_score", "sentiment_label"],
    properties={
        "sentiment_id": _STR,
        "mapped_id": _STR,
        "coin_id": _STR,
        "clean_text": _STR,
        "sentiment_score": _FLOAT,
        "sentiment_label": _STR,
        "sentiment_confidence": _FLOAT,
        "probabilities": _OBJ,
        "sentiment_model": _STR,
        "timestamp": _TS,
        "scored_at": _DATE,
    },
)

SENTIMENT_AGGREGATES_VALIDATOR = _schema(
    # Rollup nội bộ stage 4 (optional); Stage 6 đọc influence_aggregates thay vì collection này
    required=["coin_id", "window_start", "weighted_sentiment", "event_count"],
    properties={
        "coin_id": _STR,
        "timeframe": _STR,
        "window_start": _DATE,
        "weighted_sentiment": _FLOAT,
        "event_count": _INT,
        "avg_sentiment": _FLOAT,
    },
)

# ── Stage 5: Influence weighting ─────────────────────────────────────────────
WEIGHTED_EVENTS_VALIDATOR = _schema(
    required=["weighted_id", "source_event_key", "influence_weight", "weighted_sentiment"],
    properties={
        "weighted_id": _STR,
        "source_event_key": _STR,
        "sentiment_id": _STR,
        "coin_id": _STR,
        "influence_weight": _FLOAT,
        "weighted_sentiment": _FLOAT,
        "influence": _OBJ,
        "timestamp": _TS,
    },
)

INFLUENCE_AGGREGATES_VALIDATOR = _schema(
    # Input chuẩn cho Stage 6 Scoring — aggregate theo (coin, timeframe, window)
    required=["coin_id", "timeframe", "window_start", "sentiment_score", "social_volume"],
    properties={
        "coin_id": _STR,
        "timeframe": _STR,
        "window_start": _DATE,
        "sentiment_score": _FLOAT,
        "social_volume": _INT,
        "total_influence": _FLOAT,
        "event_count": _INT,
    },
)

# ── Stage 6: Scoring signals ─────────────────────────────────────────────────
SCORING_SIGNALS_VALIDATOR = _schema(
    required=["signal_id", "coin_id", "action", "timestamp"],
    properties={
        "signal_id": _STR,
        "coin_id": _STR,
        "timeframe": _STR,
        "action": {"bsonType": "string", "enum": ["BUY", "HOLD", "SELL"]},
        "metrics": _OBJ,
        "execution": _OBJ,
        "timestamp": _TS,
    },
)

# ── Stage 7 + Chat + Orchestrator ────────────────────────────────────────────
ANALYSIS_REPORTS_VALIDATOR = _schema(
    required=["report_id", "session_id", "coin_id", "summary", "generated_at"],
    properties={
        "report_id": _STR,
        "session_id": _STR,
        "signal_id": _STR,
        "coin_id": _STR,
        "timeframe": _STR,
        "summary": _STR,
        "key_findings": _ARR,
        "sections": _OBJ,
        "recommendation": _STR,
        "confidence": _FLOAT,
        "model": _STR,
        "generated_at": _DATE,
    },
)

ANALYSIS_SESSIONS_VALIDATOR = _schema(
    required=["session_id", "coin_id", "timeframe", "status", "created_at"],
    properties={
        "session_id": _STR,
        "coin_id": _STR,
        "timeframe": _STR,
        "job_id": _STR,
        "report_id": _STR,
        "status": {"bsonType": "string", "enum": ["pending", "running", "completed", "failed"]},
        "created_at": _DATE,
        "completed_at": _DATE,
    },
)

CHAT_MESSAGES_VALIDATOR = _schema(
    required=["message_id", "session_id", "role", "type", "content", "created_at"],
    properties={
        "message_id": _STR,
        "session_id": _STR,
        "role": {"bsonType": "string", "enum": ["user", "assistant", "system"]},
        "type": _STR,
        "content": _STR,
        "metadata": _OBJ,
        "created_at": _DATE,
    },
)

PIPELINE_JOBS_VALIDATOR = _schema(
    required=["job_id", "session_id", "status", "started_at"],
    properties={
        "job_id": _STR,
        "session_id": _STR,
        "status": {"bsonType": "string", "enum": ["pending", "running", "completed", "failed"]},
        "stages": _ARR,
        "started_at": _DATE,
        "finished_at": _DATE,
    },
)

PIPELINE_STAGE_RUNS_VALIDATOR = _schema(
    required=["run_id", "job_id", "stage", "status"],
    properties={
        "run_id": _STR,
        "job_id": _STR,
        "stage": _STR,
        "status": _STR,
        "records_in": _INT,
        "records_out": _INT,
        "duration_ms": _INT,
        "error": _STR,
    },
)

# Map tên collection → validator; dùng trong bootstrap._ensure_collections()
COLLECTION_VALIDATORS: dict[str, dict[str, Any]] = {
    "raw_events": RAW_EVENTS_VALIDATOR,
    "clean_events": CLEAN_EVENTS_VALIDATOR,
    "dropped_events": DROPPED_EVENTS_VALIDATOR,
    "mapped_events": MAPPED_EVENTS_VALIDATOR,
    "sentiment_events": SENTIMENT_EVENTS_VALIDATOR,
    "sentiment_aggregates": SENTIMENT_AGGREGATES_VALIDATOR,
    "weighted_events": WEIGHTED_EVENTS_VALIDATOR,
    "influence_aggregates": INFLUENCE_AGGREGATES_VALIDATOR,
    "scoring_signals": SCORING_SIGNALS_VALIDATOR,
    "analysis_reports": ANALYSIS_REPORTS_VALIDATOR,
    "analysis_sessions": ANALYSIS_SESSIONS_VALIDATOR,
    "chat_messages": CHAT_MESSAGES_VALIDATOR,
    "pipeline_jobs": PIPELINE_JOBS_VALIDATOR,
    "pipeline_stage_runs": PIPELINE_STAGE_RUNS_VALIDATOR,
}
