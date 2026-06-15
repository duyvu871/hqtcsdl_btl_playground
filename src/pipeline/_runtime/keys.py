"""Redis Streams topology — tên stream, consumer group, TTL.

Tham chiếu: docs/kien-truc-he-thong.md §5.1, phase-02 §2.2
"""

from __future__ import annotations

# Thứ tự 7 stage pipeline ETL
STAGE_ORDER: list[str] = [
    "ingest",
    "filter",
    "ner",
    "sentiment",
    "influence",
    "scoring",
    "insight",
]

# Stage → downstream input stream (insight là terminal stage)
NEXT_STREAM: dict[str, str | None] = {
    "ingest": "stage:filter:in",
    "filter": "stage:ner:in",
    "ner": "stage:sentiment:in",
    "sentiment": "stage:influence:in",
    "influence": "stage:scoring:in",
    "scoring": "stage:insight:in",
    "insight": None,
}

MAXLEN = 50_000  # backpressure trim cho stage transport streams
CTL_MAXLEN = 10_000  # trim cho session control bus


def in_stream(stage: str) -> str:
    """Input stream của stage: stage:{name}:in"""
    return f"stage:{stage}:in"


def dlq_stream(stage: str) -> str:
    """Dead-letter stream sau max retry: stage:{name}:dlq"""
    return f"stage:{stage}:dlq"


def group(stage: str) -> str:
    """Consumer group: cg:{name}"""
    return f"cg:{stage}"


def ctl_stream(session_id: str) -> str:
    """Control bus cho session: session:{id}:events"""
    return f"session:{session_id}:events"


def state_key(session_id: str) -> str:
    """Runtime counters hash: session:{id}:state"""
    return f"session:{session_id}:state"
