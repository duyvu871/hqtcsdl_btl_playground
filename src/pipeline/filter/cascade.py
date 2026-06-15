"""Cascade L1 → L2 → L3 — orchestrate filter layers.

Luồng mỗi event:
  L1 check_heuristic()  → DROP (pump_regex, min_likes, …)
  L2 dedup.is_duplicate() → DROP (simhash_duplicate)
  L3 ml.predict()       → DROP (fasttext_spam) hoặc skip nếu không có model
  PASS → FilterOutcome(stage="PASS")
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.pipeline.filter.dedup import DedupState
from src.pipeline.filter.heuristic import HeuristicConfig, check_heuristic
from src.pipeline.filter.ml import MlConfig, MlResult, SpamClassifier, default_ml_classifier


@dataclass
class FilterStats:
    """Thống kê batch — dùng cho monitoring / báo cáo."""
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
    """Kết quả 1 event qua cascade — input cho build_clean/dropped_doc."""
    passed: bool
    stage: str
    reason: str | None
    clean_text: str
    meta: dict[str, Any]


def run_single(
    event: dict[str, Any],
    *,
    heuristic: HeuristicConfig,
    ml: SpamClassifier | None = None,
    dedup: DedupState | None = None,
    author_counts: dict[str, int] | None = None,
    stats: FilterStats | None = None,
) -> FilterOutcome:
    """Chạy cascade cho 1 event — dùng trong stream worker."""
    if dedup is None:
        dedup = DedupState()
    if author_counts is None:
        author_counts = {}
    if stats is not None:
        stats.total += 1

    author = str(event.get("author_id") or "unknown")

    # ── L1: heuristic rules ──
    h = check_heuristic(event, config=heuristic, author_counts=author_counts)
    if not h.passed:
        if stats:
            stats.record_drop("L1", h.reason or "unknown")
        return FilterOutcome(False, "L1", h.reason, h.clean_text, {"layer": "heuristic", "reason": h.reason})

    # Chỉ đếm author sau khi pass L1 — cap áp dụng cho event hợp lệ
    author_counts[author] = author_counts.get(author, 0) + 1

    # ── L2: SimHash near-duplicate ──
    if dedup.is_duplicate(h.clean_text):
        if stats:
            stats.record_drop("L2", "simhash_duplicate")
        return FilterOutcome(False, "L2", "simhash_duplicate", h.clean_text, {"layer": "simhash"})

    # ── L3: FastText (skip nếu model không có hoặc source=news) ──
    ml_meta: dict[str, Any] = {"layer": "fasttext", "skipped": True}
    if ml is not None and ml.available:
        ml_result = ml.predict(event, text=h.clean_text)
        ml_meta = {
            "layer": "fasttext",
            "skipped": ml_result.skipped,
            "label": ml_result.label,
            "score": ml_result.score,
            "prob_spam": ml_result.score if ml_result.label == "spam" else 0.0,
        }
        if not ml_result.passed:
            if stats:
                stats.record_drop("L3", "fasttext_spam")
            return FilterOutcome(False, "L3", "fasttext_spam", h.clean_text, ml_meta)

    layers = ["heuristic", "simhash"] + (["fasttext"] if ml and ml.available else [])
    if stats:
        stats.passed += 1
    return FilterOutcome(
        True,
        "PASS",
        None,
        h.clean_text,
        {"stage": "passed", "layers": layers, "fasttext": ml_meta, "clean_text": h.clean_text},
    )


def run_cascade(
    events: list[dict[str, Any]],
    *,
    heuristic: HeuristicConfig | None = None,
    ml: SpamClassifier | None = None,
    dedup: DedupState | None = None,
    stats: FilterStats | None = None,
) -> tuple[list[tuple[dict[str, Any], FilterOutcome]], list[tuple[dict[str, Any], FilterOutcome]]]:
    """Chạy cascade cho batch — trả (passed, dropped)."""
    heuristic = heuristic or HeuristicConfig()
    dedup = dedup or DedupState()
    stats = stats or FilterStats()
    author_counts: dict[str, int] = {}

    passed: list[tuple[dict[str, Any], FilterOutcome]] = []
    dropped: list[tuple[dict[str, Any], FilterOutcome]] = []

    for event in events:
        outcome = run_single(
            event,
            heuristic=heuristic,
            ml=ml,
            dedup=dedup,
            author_counts=author_counts,
            stats=stats,
        )
        if outcome.passed:
            passed.append((event, outcome))
        else:
            dropped.append((event, outcome))

    return passed, dropped
