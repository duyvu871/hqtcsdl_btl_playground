"""Stage 2 — Filter: cascade L1→L2→L3 → clean/dropped events.

Entry point cho runtime: filter_processor (worker.py)
"""

from src.pipeline.filter.cascade import FilterOutcome, FilterStats, run_cascade, run_single
from src.pipeline.filter.documents import build_clean_doc, build_dropped_doc
from src.pipeline.filter.heuristic import HeuristicConfig, check_heuristic
from src.pipeline.filter.service import FilterPipeline, get_filter_pipeline, reset_filter_pipeline
from src.pipeline.filter.worker import filter_processor

__all__ = [
    "FilterOutcome",
    "FilterStats",
    "FilterPipeline",
    "HeuristicConfig",
    "build_clean_doc",
    "build_dropped_doc",
    "check_heuristic",
    "filter_processor",
    "get_filter_pipeline",
    "reset_filter_pipeline",
    "run_cascade",
    "run_single",
]
