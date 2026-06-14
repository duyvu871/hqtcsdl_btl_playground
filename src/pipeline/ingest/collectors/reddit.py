"""Reddit collector — OAuth (khuyến nghị) hoặc public JSON fallback.

OAuth: REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, REDDIT_USERNAME, REDDIT_PASSWORD
Public JSON hay bị 403 → cần OAuth cho production.
"""

from __future__ import annotations

import base64
import json
import logging
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from src.common.config import settings
from src.pipeline.ingest.events import reddit_to_raw_event

logger = logging.getLogger(__name__)

OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_API_BASE = "https://oauth.reddit.com"
PUBLIC_BASES = ("https://old.reddit.com", "https://www.reddit.com")

_token_cache: tuple[str, float] | None = None  # (access_token, expires_at)


def _reddit_oauth_configured() -> bool:
    return bool(settings.REDDIT_CLIENT_ID and settings.REDDIT_USERNAME and settings.REDDIT_PASSWORD)


def _request_headers(*, token: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": settings.REDDIT_USER_AGENT,
        "Accept": "application/json, text/plain, */*",
    }
    if token:
        headers["Authorization"] = f"bearer {token}"
    return headers


def _oauth_access_token() -> str:
    global _token_cache

    if not _reddit_oauth_configured():
        raise RuntimeError("Reddit OAuth chưa cấu hình trong .env")

    now = time.time()
    if _token_cache and now < _token_cache[1] - 60:
        return _token_cache[0]

    client_id = settings.REDDIT_CLIENT_ID
    secret = settings.REDDIT_CLIENT_SECRET or ""
    auth = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "username": settings.REDDIT_USERNAME,
            "password": settings.REDDIT_PASSWORD,
        }
    ).encode()

    req = urllib.request.Request(
        OAUTH_TOKEN_URL,
        data=body,
        headers={
            **_request_headers(),
            "Authorization": f"Basic {auth}",
            "Content-Type": "application/x-www-form-urlencoded",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            payload = json.loads(resp.read().decode("utf-8", errors="replace"))
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Reddit OAuth HTTP {e.code}: {err[:300]}") from e

    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"Reddit OAuth không trả access_token: {payload!r}")

    expires_in = float(payload.get("expires_in", 3600))
    _token_cache = (token, now + expires_in)
    return token


def _fetch_oauth(path: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({**params, "raw_json": "1"})
    url = f"{OAUTH_API_BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers=_request_headers(token=token), method="GET")
    with urllib.request.urlopen(req, timeout=60) as resp:
        data = json.loads(resp.read().decode("utf-8", errors="replace"))
    if not isinstance(data, dict):
        raise RuntimeError("Reddit: invalid JSON")
    return data


def _fetch_public(path: str, params: dict[str, Any]) -> dict[str, Any]:
    qs = urllib.parse.urlencode({**params, "raw_json": "1"})
    last_error = "unknown"

    for base in PUBLIC_BASES:
        url = f"{base}{path}.json?{qs}"
        req = urllib.request.Request(url, headers=_request_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                data = json.loads(resp.read().decode("utf-8", errors="replace"))
            if isinstance(data, dict):
                return data
            last_error = f"{base}: not object"
        except urllib.error.HTTPError as e:
            last_error = f"{base}: HTTP {e.code}"
            if e.code != 403:
                raise RuntimeError(f"Reddit {last_error}") from e
        except urllib.error.URLError as e:
            last_error = f"{base}: {e.reason}"

    raise RuntimeError(f"Reddit public JSON blocked ({last_error}). Cần OAuth trong .env.")


def _fetch_listing(path: str, params: dict[str, Any]) -> dict[str, Any]:
    if _reddit_oauth_configured():
        return _fetch_oauth(path, params, _oauth_access_token())
    return _fetch_public(path, params)


def collect_reddit_events(
    *,
    subreddit: str = "cryptocurrency",
    query: str = "bitcoin OR ethereum OR BTC OR ETH",
    sort: str = "new",
    limit: int = 25,
    listing: str = "search",
) -> list[dict[str, Any]]:
    sub = subreddit.strip().lstrip("r/") or "cryptocurrency"
    lim = max(1, min(100, limit))

    if listing == "hot":
        path, params = f"/r/{sub}/hot", {"limit": lim}
    elif listing == "new":
        path, params = f"/r/{sub}/new", {"limit": lim}
    else:
        path = f"/r/{sub}/search"
        params = {
            "q": query,
            "restrict_sr": "true",
            "sort": sort,
            "limit": lim,
            "type": "link",
        }

    payload = _fetch_listing(path, params)
    children = (payload.get("data") or {}).get("children") or []
    if not isinstance(children, list):
        return []

    seen_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    for child in children:
        if not isinstance(child, dict):
            continue
        post = child.get("data")
        if not isinstance(post, dict):
            continue
        post_id = str(post.get("name") or post.get("id") or "")
        if post_id and post_id in seen_ids:
            continue
        if post_id:
            seen_ids.add(post_id)
        events.append(reddit_to_raw_event(post))

    logger.info("Reddit r/%s: collected %d events", sub, len(events))
    return events
