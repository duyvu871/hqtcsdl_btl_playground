"""Stage 3 — NER & coin mapping (fan-out mapped_events)."""

from src.pipeline.ner.documents import build_mapped_docs
from src.pipeline.ner.pipeline import NerMode, NerOutcome, NerStats, map_event
from src.pipeline.ner.registry import CoinRegistry
from src.pipeline.ner.rules import Mention, RuleResult, extract_rules
from src.pipeline.ner.service import NerPipeline, get_ner_pipeline, reset_ner_pipeline
from src.pipeline.ner.worker import ner_processor

__all__ = [
    "CoinRegistry",
    "Mention",
    "NerMode",
    "NerOutcome",
    "NerPipeline",
    "NerStats",
    "RuleResult",
    "build_mapped_docs",
    "extract_rules",
    "get_ner_pipeline",
    "map_event",
    "ner_processor",
    "reset_ner_pipeline",
]
