#!/usr/bin/env python3
"""
Helpers cho playground Yahoo Finance: serialize pandas / object -> JSON-safe.
"""

from __future__ import annotations

import json
import math
from datetime import date, datetime
from typing import Any


def json_sanitize(obj: Any) -> Any:
    """Chuyển object thành cấu trúc có thể json.dump (NaN → null, Timestamp → iso)."""
    if obj is None or isinstance(obj, (str, bool, int)):
        return obj
    if isinstance(obj, float):
        return None if math.isnan(obj) else obj
    if isinstance(obj, dict):
        return {str(k): json_sanitize(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [json_sanitize(x) for x in obj]
    if isinstance(obj, (datetime, date)):
        return obj.isoformat()
    # pandas Timestamp
    try:
        if hasattr(obj, "isoformat"):
            return obj.isoformat()
    except Exception:
        pass
    return str(obj)


def dataframe_to_records(df: Any) -> list[dict[str, Any]]:
    """pandas DataFrame -> list[dict]; cột Datetime trong index được đưa vào records."""
    if df is None or getattr(df, "empty", True):
        return []
    try:
        out = df.reset_index()
        # to_json đã xử lý timestamp
        txt = out.to_json(orient="records", date_format="iso")
        parsed = json.loads(txt)
        return json_sanitize(parsed)
    except Exception as e:
        return [{"_error": str(e), "_repr": repr(df)}]


def pretty_snippet(payload: dict[str, Any] | list[Any], max_len: int = 1600) -> str:
    s = json.dumps(payload, indent=2, ensure_ascii=False)
    if len(s) > max_len:
        return s[:max_len] + f"\n... ({len(s) - max_len} ký tự)"
    return s


def render_markdown(*, descriptor: str, cmd: str, payload: dict[str, Any] | list[Any]) -> str:
    """Markdown để đọc / agent."""
    body = json.dumps(payload, indent=2, ensure_ascii=False)
    max_body = 12000
    if len(body) > max_body:
        body_snip = body[:max_body] + f"\n\n... ({len(body) - max_body} ký tự không hiển thị)"
    else:
        body_snip = body

    if "```" in body_snip:
        fence_open, fence_close = "~~~json\n", "\n~~~"
    else:
        fence_open, fence_close = "```json\n", "\n```"

    return (
        f"# Yahoo Finance (yfinance)\n\n"
        f"- **command:** `{cmd}`\n\n"
        f"## Request (descriptor)\n\n"
        f"```text\n{descriptor}\n```\n\n"
        f"## Response\n\n"
        f"{fence_open}{body_snip}{fence_close}\n"
    )
