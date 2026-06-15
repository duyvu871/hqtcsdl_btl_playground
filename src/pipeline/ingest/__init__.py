"""Stage 1 — Ingest: thu thập đa nguồn → raw_events.

Entry point cho runtime: ingest_processor (worker.py)
"""

from src.pipeline.ingest.service import collect_from_kickoff
from src.pipeline.ingest.worker import ingest_processor

__all__ = ["collect_from_kickoff", "ingest_processor"]
