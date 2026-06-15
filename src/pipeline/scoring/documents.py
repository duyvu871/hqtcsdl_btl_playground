"""Map scoring result → scoring_signals document."""

from __future__ import annotations

import uuid
from typing import Any


def build_scoring_signal(
    *,
    coin_id: str,
    timeframe: str,
    action: str,
    metrics: dict[str, Any],
    execution: dict[str, Any],
    timestamp: int,
) -> dict[str, Any]:
    return {
        "signal_id": str(uuid.uuid4()),
        "coin_id": coin_id,
        "timeframe": timeframe,
        "action": action,
        "metrics": metrics,
        "execution": execution,
        "timestamp": timestamp,
    }
