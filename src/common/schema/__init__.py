"""MongoDB schema — collections, validators, models, bootstrap.

Public API của tầng dữ liệu P1:
  - COLLECTIONS: danh sách 14 collection
  - bootstrap_indexes(db): khởi tạo DB
  - RawEvent, CleanEvent, ...: Pydantic models
  - COLLECTION_VALIDATORS: $jsonSchema dicts
"""

from __future__ import annotations

from src.common.schema.bootstrap import bootstrap_indexes
from src.common.schema.models import (
    AnalysisReport,
    AnalysisSession,
    ChatMessage,
    CleanEvent,
    DroppedEvent,
    InfluenceAggregate,
    MappedEvent,
    PipelineJob,
    PipelineStageRun,
    RawEvent,
    ScoringSignal,
    SentimentAggregate,
    SentimentEvent,
    WeightedEvent,
)
from src.common.schema.validators import COLLECTION_VALIDATORS

# 14 collection theo ERD docs/diagrams/khung-bao-cao/05-erd-mongodb.puml
COLLECTIONS: list[str] = [
    "raw_events",
    "clean_events",
    "dropped_events",
    "mapped_events",
    "sentiment_events",
    "sentiment_aggregates",
    "weighted_events",
    "influence_aggregates",
    "scoring_signals",
    "analysis_reports",
    "analysis_sessions",
    "chat_messages",
    "pipeline_jobs",
    "pipeline_stage_runs",
]

__all__ = [
    "COLLECTIONS",
    "COLLECTION_VALIDATORS",
    "AnalysisReport",
    "AnalysisSession",
    "ChatMessage",
    "CleanEvent",
    "DroppedEvent",
    "InfluenceAggregate",
    "MappedEvent",
    "PipelineJob",
    "PipelineStageRun",
    "RawEvent",
    "ScoringSignal",
    "SentimentAggregate",
    "SentimentEvent",
    "WeightedEvent",
    "bootstrap_indexes",
]
