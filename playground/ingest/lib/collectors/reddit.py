"""Reddit — OAuth API (khuyến nghị) hoặc public JSON fallback."""

from __future__ import annotations

import base64
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import TYPE_CHECKING, Any

from lib.config import (
    reddit_client_id,
    reddit_client_secret,
    reddit_oauth_configured,
    reddit_password,
    reddit_user_agent,
    reddit_username,
)
from lib.events import reddit_to_raw_event

if TYPE_CHECKING:
    from lib.progress import Progress

OAUTH_TOKEN_URL = "https://www.reddit.com/api/v1/access_token"
OAUTH_API_BASE = "https://oauth.reddit.com"
PUBLIC_BASES = ("https://old.reddit.com", "https://www.reddit.com")

_token_cache: tuple[str, float] | None = None


def _request_headers(*, token: str | None = None) -> dict[str, str]:
    headers = {
        "User-Agent": reddit_user_agent(),
        "Accept": "application/json, text/plain, */*",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if token:
        headers["Authorization"] = f"bearer {token}"
    return headers


def _oauth_access_token() -> str:
    global _token_cache

    client_id = reddit_client_id()
    username = reddit_username()
    password = reddit_password()
    if not client_id or not username or not password:
        raise RuntimeError(
            "Reddit yêu cầu OAuth. Tạo app tại https://www.reddit.com/prefs/apps "
            '(loại "script") rồi điền REDDIT_CLIENT_ID, REDDIT_CLIENT_SECRET, '
            "REDDIT_USERNAME, REDDIT_PASSWORD vào .env."
        )

    now = time.time()
    if _token_cache and now < _token_cache[1] - 60:
        return _token_cache[0]

    secret = reddit_client_secret() or ""
    auth = base64.b64encode(f"{client_id}:{secret}".encode()).decode()
    body = urllib.parse.urlencode(
        {
            "grant_type": "password",
            "username": username,
            "password": password,
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
        raise RuntimeError(
            f"Reddit OAuth token HTTP {e.code}: {err[:300]}\n"
            "Kiểm tra REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD trong .env."
        ) from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Reddit OAuth token failed: {e.reason}") from e

    token = payload.get("access_token")
    if not isinstance(token, str) or not token:
        raise RuntimeError(f"Reddit OAuth không trả access_token: {payload!r}")

    expires_in = payload.get("expires_in", 3600)
    if not isinstance(expires_in, (int, float)):
        expires_in = 3600
    _token_cache = (token, now + float(expires_in))
    return token


def _fetch_oauth(path: str, params: dict[str, Any], token: str) -> dict[str, Any]:
    qs = urllib.parse.urlencode({**params, "raw_json": "1"})
    url = f"{OAUTH_API_BASE}{path}?{qs}"
    req = urllib.request.Request(url, headers=_request_headers(token=token), method="GET")

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err = e.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Reddit OAuth HTTP {e.code}: {err[:300]}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"Reddit OAuth request failed: {e.reason}") from e

    data = json.loads(body)
    if not isinstance(data, dict):
        raise RuntimeError("Reddit trả về JSON không hợp lệ")
    return data


def _fetch_public(path: str, params: dict[str, Any]) -> dict[str, Any]:
    qs = urllib.parse.urlencode({**params, "raw_json": "1"})
    last_error = "unknown"

    for base in PUBLIC_BASES:
        url = f"{base}{path}.json?{qs}"
        req = urllib.request.Request(url, headers=_request_headers(), method="GET")
        try:
            with urllib.request.urlopen(req, timeout=60) as resp:
                body = resp.read().decode("utf-8", errors="replace")
            data = json.loads(body)
            if isinstance(data, dict):
                return data
            last_error = f"{base}: JSON không phải object"
        except urllib.error.HTTPError as e:
            err = e.read().decode("utf-8", errors="replace")
            last_error = f"{base}: HTTP {e.code}"
            if e.code != 403:
                raise RuntimeError(f"Reddit {last_error}: {err[:200]}") from e
        except urllib.error.URLError as e:
            last_error = f"{base}: {e.reason}"

    raise RuntimeError(
        f"Reddit public JSON bị chặn ({last_error}). "
        "Điền OAuth vào .env — xem playground/ingest/README.md mục Reddit."
    )


def _fetch_listing(path: str, params: dict[str, Any]) -> dict[str, Any]:
    if reddit_oauth_configured():
        token = _oauth_access_token()
        return _fetch_oauth(path, params, token)
    return _fetch_public(path, params)


def collect_reddit_events(
    *,
    subreddit: str = "cryptocurrency",
    query: str = "bitcoin OR ethereum OR BTC OR ETH",
    sort: str = "new",
    limit: int = 25,
    listing: str = "search",
    progress: Progress | None = None,
) -> list[dict[str, Any]]:
    sub = subreddit.strip().lstrip("r/") or "cryptocurrency"
    lim = max(1, min(100, limit))

    if listing == "hot":
        path = f"/r/{sub}/hot"
        params: dict[str, Any] = {"limit": lim}
    elif listing == "new":
        path = f"/r/{sub}/new"
        params = {"limit": lim}
    else:
        path = f"/r/{sub}/search"
        params = {
            "q": query,
            "restrict_sr": "true",
            "sort": sort,
            "limit": lim,
            "type": "link",
        }

    mode = "OAuth" if reddit_oauth_configured() else "public JSON"
    if progress:
        progress.log(f"Reddit r/{sub} ({listing}, {mode}): đang gọi API...")

    payload = _fetch_listing(path, params)
    children = (payload.get("data") or {}).get("children") or []
    if not isinstance(children, list):
        if progress:
            progress.log("Reddit: không có bài.")
        return []

    seen_ids: set[str] = set()
    events: list[dict[str, Any]] = []
    total = len(children)
    if progress:
        progress.log(f"Reddit: xử lý {total} post...")

    done = 0
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
        done += 1
        if progress:
            progress.bar(done, total, prefix="Reddit: ")

    if progress:
        progress.log(f"Reddit: {len(events)} event(s).")

    return events
