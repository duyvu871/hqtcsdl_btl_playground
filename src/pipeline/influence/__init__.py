"""Stage 5 — Influence weighting + aggregate rollup."""

from src.pipeline.influence.aggregate import (
    aggregate_for_event,
    aggregate_weighted_events,
    fetch_recent_aggregates,
)
from src.pipeline.influence.documents import (
    aggregate_to_social_row,
    build_scoring_trigger,
    build_weighted_event,
    source_event_key,
)
from src.pipeline.influence.scoring import calculate_influence, raw_engagement
from src.pipeline.influence.service import (
    InfluencePipeline,
    get_influence_pipeline,
    reset_influence_pipeline,
)
from src.pipeline.influence.worker import influence_processor

__all__ = [
    "InfluencePipeline",
    "aggregate_for_event",
    "aggregate_to_social_row",
    "aggregate_weighted_events",
    "build_scoring_trigger",
    "build_weighted_event",
    "calculate_influence",
    "fetch_recent_aggregates",
    "get_influence_pipeline",
    "influence_processor",
    "raw_engagement",
    "reset_influence_pipeline",
    "source_event_key",
]
