"""Stage 3 business logic — hybrid NER + fan-out mapped_events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.common.config import settings
from src.pipeline.ner.documents import build_mapped_docs
from src.pipeline.ner.llm import OpenRouterNER
from src.pipeline.ner.pipeline import NerMode, NerOutcome, NerStats, map_event
from src.pipeline.ner.registry import CoinRegistry


@dataclass
class NerPipeline:
    """Stateful NER — registry + optional LLM load 1 lần per worker."""

    mode: NerMode = field(default_factory=lambda: NerMode.parse(settings.NER_MODE))
    registry: CoinRegistry = field(default_factory=CoinRegistry.load)
    llm: OpenRouterNER | None = None
    stats: NerStats = field(default_factory=NerStats)

    def __post_init__(self) -> None:
        if settings.OPENROUTER_API_KEY:
            self.llm = OpenRouterNER()
        else:
            self.llm = None

    def process(self, clean_event: dict[str, Any]) -> tuple[NerOutcome, list[dict[str, Any]]]:
        outcome = map_event(
            clean_event,
            mode=self.mode,
            registry=self.registry,
            llm=self.llm,
        )
        docs = build_mapped_docs(clean_event, outcome.mentions, outcome)
        self.stats.record(outcome, fanout_count=len(docs))
        return outcome, docs


_pipeline: NerPipeline | None = None


def get_ner_pipeline() -> NerPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = NerPipeline()
    return _pipeline


def reset_ner_pipeline() -> None:
    global _pipeline
    _pipeline = None
