#!/usr/bin/env python3
"""
Alpha Vantage – HTTP GET tối giản + in request (ẩn apikey).

Không pull code từ TradingAgents; chỉ stdlib.
"""

from __future__ import annotations

import json
import os
import ssl
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime
from typing import Any

BASE_URL = "https://www.alphavantage.co/query"

_REQUEST_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/csv,text/plain,text/html,*/*;q=0.8",
}


def _ssl_context() -> ssl.SSLContext:
    ctx = ssl.create_default_context()
    # Một môi trường chỉ có TLS hơi kỳ — không bật VERIFY_NONE (an toàn mặc định).
    return ctx


def get_api_key() -> str:
    k = os.environ.get("ALPHA_VANTAGE_API_KEY", "").strip()
    if not k:
        raise SystemExit(
            "Thiếu ALPHA_VANTAGE_API_KEY. Ví dụ:\n"
            '  export ALPHA_VANTAGE_API_KEY="your-key"'
        )
    return k


def to_av_time(dt: datetime) -> str:
    """Định dạng NEWS_SENTIMENT: YYYYMMDDTHHMM."""
    return dt.strftime("%Y%m%dT%H%M")


def redacted_query(params: dict[str, Any]) -> str:
    """Query string để log (ẩn apikey)."""
    pub = dict(params)
    if "apikey" in pub:
        pub["apikey"] = "***"
    return urllib.parse.urlencode(pub)


def fetch(params: dict[str, Any]) -> tuple[str, str]:
    """
    GET Alpha Vantage. Trả về (url_display_redacted, body_text).

    Thử lại với backoff khi lỗi mạng tạm (Connection reset, timeout, …).
    """
    api_key = get_api_key()
    full = dict(params)
    full["apikey"] = api_key
    qs = urllib.parse.urlencode(full)
    url = f"{BASE_URL}?{qs}"
    disp = f"{BASE_URL}?{redacted_query(full)}"

    req = urllib.request.Request(url, headers=_REQUEST_HEADERS)
    ctx = _ssl_context()
    timeout_s = 90
    backoff_sec = [0.0, 1.5, 3.5, 7.0]
    last_exc: BaseException | None = None

    for attempt in range(len(backoff_sec)):
        if backoff_sec[attempt]:
            time.sleep(backoff_sec[attempt])
        try:
            with urllib.request.urlopen(req, timeout=timeout_s, context=ctx) as resp:
                body = resp.read().decode("utf-8", errors="replace")
                return disp, body
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            return disp, f"[HTTP {e.code}] {err_body}"
        except (urllib.error.URLError, TimeoutError, OSError, ConnectionError) as e:
            last_exc = e
            continue

    hint = (
        "\nGợi ý:\n"
        "  • Firewall/VPN/proxy (mạng trường/công ty hay reset kết nối HTTPS).\n"
        "  • Thử sau vài giây; kiểm tra: curl -sI https://www.alphavantage.co/\n"
        "  • Nếu vẫn lỗi: dùng mạng khác hoặc cài requests (script vẫn dùng urllib).\n"
    )
    detail = getattr(last_exc, "reason", None) or last_exc
    raise SystemExit(f"Lỗi kết nối sau {len(backoff_sec)} lần thử: {detail!s}{hint}") from last_exc


def pretty_snippet(raw: str, max_len: int = 1200) -> str:
    """Cố gắng pretty-print JSON nếu được; không thì cắt chuỗi."""
    raw = raw.strip()
    try:
        obj = json.loads(raw)
        s = json.dumps(obj, indent=2, ensure_ascii=False)
        if len(s) > max_len:
            return s[:max_len] + f"\n... ({len(s) - max_len} ký tự còn lại)"
        return s
    except json.JSONDecodeError:
        # CSV hoặc text
        return raw[:max_len] + ("..." if len(raw) > max_len else "")


def parse_body_as_json_or_raw(body: str) -> dict[str, Any]:
    """Chuẩn hóa body để ghi JSON: parse được thì object/list bọc lại, không thì raw."""
    body = body.strip()
    try:
        parsed = json.loads(body)
        if isinstance(parsed, dict):
            return dict(parsed)
        return {"_data": parsed}
    except json.JSONDecodeError:
        return {"format": "text_or_csv", "raw": body}


def render_markdown(*, url_disp: str, body: str, cmd: str) -> str:
    """Markdown để đọc / đưa cho agent."""
    preview = pretty_snippet(body, max_len=8000)
    lines = [
        "# Alpha Vantage response",
        "",
        f"- **command:** `{cmd}`",
        "",
        "## Request",
        "",
        "```text",
        url_disp,
        "```",
        "",
        "## Response",
        "",
    ]
    if "```" in preview:
        lines.extend(["~~~text", preview, "~~~"])
    else:
        lines.extend(["```json", preview, "```"])
    lines.append("")
    return "\n".join(lines)
