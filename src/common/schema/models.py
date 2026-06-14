"""Pydantic v2 document models for MongoDB collections (app-level validation).

Lớp validation thứ hai (app-level): validate trước khi ghi DB.
Dùng pattern: RawEvent.model_validate(data).model_dump() → upsert_stage(...)

Cặp với validators.py ($jsonSchema) để có 2 lớp bảo vệ dữ liệu.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class _MongoModel(BaseModel):
    """Base model — extra='allow' để stage sau có thể thêm field mà không phá model cũ."""

    model_config = ConfigDict(extra="allow")


# ── Stage 1 ──────────────────────────────────────────────────────────────────
class RawEvent(_MongoModel):
    event_id: str
    source: Literal["reddit", "twitter", "telegram", "news"]
    raw_text: str
    timestamp: datetime | int  # unix int (pipeline) hoặc datetime (API)
    external_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    author_id: str | None = None
    ingested_at: datetime | int | None = None
    language: str | None = None


# ── Stage 2 ──────────────────────────────────────────────────────────────────
class CleanEvent(_MongoModel):
    event_id: str
    clean_text: str
    timestamp: datetime | int  # unix int (pipeline) hoặc datetime (API)
    parent_event_id: str | None = None
    clean_id: str | None = None
    source: str | None = None
    filter: dict[str, Any] = Field(default_factory=dict)
    is_spam: bool = False
    author_id: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)


class DroppedEvent(_MongoModel):
    """Event bị loại bởi filter cascade — dùng cho audit FR-02."""
    event_id: str
    drop_stage: str
    drop_reason: str
    filter: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | int | None = None
    source: str | None = None
    raw_text: str | None = None


# ── Stage 3 ──────────────────────────────────────────────────────────────────
class MappedEvent(_MongoModel):
    """1 document / coin / post — fan-out từ clean_events."""
    mapped_id: str
    parent_event_id: str
    coin_id: str
    event_id: str | None = None
    source: str | None = None
    clean_text: str | None = None
    ner: dict[str, Any] = Field(default_factory=dict)
    ner_method: str | None = None
    mentions: list[str] = Field(default_factory=list)
    timestamp: datetime | int | None = None


# ── Stage 4 ──────────────────────────────────────────────────────────────────
class SentimentEvent(_MongoModel):
    sentiment_id: str
    mapped_id: str
    coin_id: str
    sentiment_score: float
    sentiment_label: str
    clean_text: str | None = None
    sentiment_confidence: float | None = None
    probabilities: dict[str, float] = Field(default_factory=dict)
    sentiment_model: str | None = None
    timestamp: datetime | int | None = None
    scored_at: datetime | None = None


class SentimentAggregate(_MongoModel):
    """Rollup nội bộ stage 4 (optional)."""
    coin_id: str
    window_start: datetime
    weighted_sentiment: float
    event_count: int
    timeframe: str | None = None
    avg_sentiment: float | None = None


# ── Stage 5 ──────────────────────────────────────────────────────────────────
class WeightedEvent(_MongoModel):
    weighted_id: str
    source_event_key: str
    influence_weight: float
    weighted_sentiment: float
    sentiment_id: str | None = None
    coin_id: str | None = None
    influence: dict[str, Any] = Field(default_factory=dict)
    timestamp: datetime | int | None = None


class InfluenceAggregate(_MongoModel):
    """Aggregate window — input chuẩn cho Stage 6 Scoring."""
    coin_id: str
    timeframe: str
    window_start: datetime
    sentiment_score: float
    social_volume: int
    total_influence: float | None = None
    event_count: int | None = None


# ── Stage 6 ──────────────────────────────────────────────────────────────────
class ScoringSignal(_MongoModel):
    signal_id: str
    coin_id: str
    action: Literal["BUY", "HOLD", "SELL"]
    timestamp: datetime | int  # unix int (pipeline) hoặc datetime (API)
    timeframe: str | None = None
    metrics: dict[str, Any] = Field(default_factory=dict)
    execution: dict[str, Any] = Field(default_factory=dict)


# ── Stage 7 + Chat + Orchestrator ────────────────────────────────────────────
class AnalysisReport(_MongoModel):
    report_id: str
    session_id: str
    coin_id: str
    summary: str
    generated_at: datetime
    signal_id: str | None = None
    timeframe: str | None = None
    key_findings: list[str] = Field(default_factory=list)
    sections: dict[str, str] = Field(default_factory=dict)
    recommendation: str | None = None
    confidence: float | None = None
    model: str | None = None


class AnalysisSession(_MongoModel):
    session_id: str
    coin_id: str
    timeframe: str
    status: Literal["pending", "running", "completed", "failed"]
    created_at: datetime
    job_id: str | None = None
    report_id: str | None = None
    completed_at: datetime | None = None


class ChatMessage(_MongoModel):
    """Lịch sử chat theo session — FR-13."""
    message_id: str
    session_id: str
    role: Literal["user", "assistant", "system"]
    type: str
    content: str
    created_at: datetime
    metadata: dict[str, Any] = Field(default_factory=dict)


class PipelineJob(_MongoModel):
    """Job ETL gắn với analysis session — do Orchestrator quản lý."""
    job_id: str
    session_id: str
    status: Literal["pending", "running", "completed", "failed"]
    started_at: datetime
    stages: list[dict[str, Any]] = Field(default_factory=list)
    finished_at: datetime | None = None


class PipelineStageRun(_MongoModel):
    """Chi tiết chạy từng stage trong một job — metrics records_in/out, duration_ms."""
    run_id: str
    job_id: str
    stage: str
    status: str
    records_in: int | None = None
    records_out: int | None = None
    duration_ms: int | None = None
    error: str | None = None
