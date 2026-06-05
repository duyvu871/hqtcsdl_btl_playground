"""Cascade L1 → L2 → L3 cho raw events."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from lib.dedup import DedupState
from lib.heuristic import HeuristicConfig, check_heuristic
from lib.ml import MlConfig, SpamClassifier


@dataclass
class FilterStats:
    total: int = 0
    passed: int = 0
    dropped_l1: int = 0
    dropped_l2: int = 0
    dropped_l3: int = 0
    by_reason: dict[str, int] = field(default_factory=dict)

    def record_drop(self, stage: str, reason: str) -> None:
        key = f"{stage}:{reason}"
        self.by_reason[key] = self.by_reason.get(key, 0) + 1
        if stage == "L1":
            self.dropped_l1 += 1
        elif stage == "L2":
            self.dropped_l2 += 1
        elif stage == "L3":
            self.dropped_l3 += 1


@dataclass(frozen=True)
class FilterOutcome:
    passed: bool
    stage: str
    reason: str | None
    clean_text: str
    meta: dict[str, Any]


def run_cascade(
    events: list[dict[str, Any]],
    *,
    heuristic: HeuristicConfig,
    ml: SpamClassifier | None = None,
    dedup: DedupState | None = None,
    stats: FilterStats | None = None,
) -> tuple[list[tuple[dict[str, Any], FilterOutcome]], list[tuple[dict[str, Any], FilterOutcome]]]:
    """
    Trả về (passed, dropped) — mỗi phần tử là (raw_event, outcome).
    """
    if dedup is None:
        dedup = DedupState()
    if stats is None:
        stats = FilterStats()

    author_counts: dict[str, int] = {}
    passed: list[tuple[dict[str, Any], FilterOutcome]] = []
    dropped: list[tuple[dict[str, Any], FilterOutcome]] = []

    for event in events:
        stats.total += 1
        author = str(event.get("author_id") or "unknown")

        h = check_heuristic(event, config=heuristic, author_counts=author_counts)
        if not h.passed:
            outcome = FilterOutcome(
                passed=False,
                stage="L1",
                reason=h.reason,
                clean_text=h.clean_text,
                meta={"layer": "heuristic", "reason": h.reason},
            )
            dropped.append((event, outcome))
            stats.record_drop("L1", h.reason or "unknown")
            continue

        author_counts[author] = author_counts.get(author, 0) + 1

        if dedup.is_duplicate(h.clean_text):
            outcome = FilterOutcome(
                passed=False,
                stage="L2",
                reason="simhash_duplicate",
                clean_text=h.clean_text,
                meta={"layer": "simhash"},
            )
            dropped.append((event, outcome))
            stats.record_drop("L2", "simhash_duplicate")
            continue

        ml_meta: dict[str, Any] = {"layer": "fasttext", "skipped": True}
        if ml is not None and ml.available:
            ml_result = ml.predict(event, text=h.clean_text)
            ml_meta = {
                "layer": "fasttext",
                "skipped": ml_result.skipped,
                "label": ml_result.label,
                "score": ml_result.score,
            }
            if not ml_result.passed:
                outcome = FilterOutcome(
                    passed=False,
                    stage="L3",
                    reason="fasttext_spam",
                    clean_text=h.clean_text,
                    meta=ml_meta,
                )
                dropped.append((event, outcome))
                stats.record_drop("L3", "fasttext_spam")
                continue

        outcome = FilterOutcome(
            passed=True,
            stage="PASS",
            reason=None,
            clean_text=h.clean_text,
            meta={
                "layers": ["heuristic", "simhash"]
                + (["fasttext"] if ml and ml.available else []),
                "fasttext": ml_meta,
            },
        )
        passed.append((event, outcome))
        stats.passed += 1

    return passed, dropped


def default_ml_classifier() -> SpamClassifier:
    from lib.config import fasttext_model_path

    return SpamClassifier(MlConfig(model_path=fasttext_model_path()))
