"""Stage 2 business logic — cascade filter + document builders.

FilterPipeline giữ state xuyên suốt worker process:
  - DedupState: SimHash index (L2)
  - author_counts: cap số post/author (L1)
  - SpamClassifier: load 1 lần (L3)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.pipeline.filter.cascade import FilterOutcome, FilterStats, run_single
from src.pipeline.filter.dedup import DedupState
from src.pipeline.filter.documents import build_clean_doc, build_dropped_doc
from src.pipeline.filter.heuristic import HeuristicConfig
from src.pipeline.filter.ml import SpamClassifier, default_ml_classifier


@dataclass
class FilterPipeline:
    """
    Stateful filter — DedupState + author_counts sống trong lifetime worker.
    Pattern: tạo 1 instance per worker process, không tạo mới mỗi message.
    """

    heuristic: HeuristicConfig = field(default_factory=HeuristicConfig)
    ml: SpamClassifier | None = None
    dedup: DedupState = field(default_factory=DedupState)
    author_counts: dict[str, int] = field(default_factory=dict)
    stats: FilterStats = field(default_factory=FilterStats)

    def __post_init__(self) -> None:
        if self.ml is None:
            self.ml = default_ml_classifier()

    def process(self, raw: dict[str, Any]) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
        """
        Chạy cascade 1 event.
        Trả (clean_doc, dropped_doc) — đúng 1 trong 2 là None.
        """
        outcome = run_single(
            raw,
            heuristic=self.heuristic,
            ml=self.ml,
            dedup=self.dedup,
            author_counts=self.author_counts,
            stats=self.stats,
        )
        if outcome.passed:
            return build_clean_doc(raw, outcome), None
        return None, build_dropped_doc(raw, outcome)


# Singleton per worker process
_pipeline: FilterPipeline | None = None


def get_filter_pipeline() -> FilterPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = FilterPipeline()
    return _pipeline


def reset_filter_pipeline() -> None:
    """Reset state — dùng trong tests."""
    global _pipeline
    _pipeline = None
