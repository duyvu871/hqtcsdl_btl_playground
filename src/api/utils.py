"""JSON helpers cho API responses."""

from __future__ import annotations

from datetime import datetime
from typing import Any


def json_safe(value: Any) -> Any:
    """Chuyển MongoDB doc → JSON-serializable."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [json_safe(v) for v in value]
    if hasattr(value, "hex"):  # ObjectId
        return str(value)
    return value


def strip_mongo_id(doc: dict[str, Any] | None) -> dict[str, Any] | None:
    if not doc:
        return doc
    out = dict(doc)
    out.pop("_id", None)
    return json_safe(out)
