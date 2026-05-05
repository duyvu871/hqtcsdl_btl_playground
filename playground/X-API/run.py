#!/usr/bin/env python3
"""
Query X search via RapidAPI (twitter154), follow continuation_token, write JSON (+ optional Markdown).

Requires:
  export RAPIDAPI_KEY="your-rapidapi-key"

Defaults favor higher-signal posts (fewer meme/shill magnets, higher engagement floors,
recent window, diversity per author). Tune with CLI flags.

Example:
  python run.py
  python run.py --markdown
  python run.py --max-pages 5 --limit 20 --md-out report.md
"""

from __future__ import annotations

import argparse
import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

BASE_URL = "https://twitter154.p.rapidapi.com/search/search"
# Orient toward market-moving / discussion-heavy crypto conversation, not pump keywords.
DEFAULT_QUERY = (
    "(bitcoin OR BTC OR ethereum OR ETH OR cryptocurrency OR crypto) "
    "(ETF OR Nasdaq OR market OR CPI OR inflation OR Fed OR treasury OR regulation OR macro OR reserve OR halving OR "
    "breaking OR merger OR subpoena OR outage OR roadmap OR bankrupt OR futures OR staking OR Layer2 OR scaling OR quarterly)"
)

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = _SCRIPT_DIR / "search_results.json"


def _simplify_tweet(raw: dict[str, Any]) -> dict[str, Any]:
    """Map API fields to a small, stable shape for agents."""
    u = raw.get("user")
    if isinstance(u, dict):
        screen = u.get("screen_name") or u.get("username")
    else:
        screen = raw.get("screen_name") or raw.get("user_username")

    text = raw.get("text")
    if text is not None:
        text = str(text).replace("\r\n", "\n").replace("\r", "\n")

    fav = raw.get("favorites")
    if fav is None:
        fav = raw.get("favorite_count")
    rts = raw.get("retweets")
    if rts is None:
        rts = raw.get("retweet_count")

    created = raw.get("created_at") or raw.get("creation_date")

    return {
        "user": screen,
        "text": text,
        "favorite_count": fav,
        "retweet_count": rts,
        "created_at": created,
    }


def _apply_max_per_user(rows: list[dict[str, Any]], cap: int) -> list[dict[str, Any]]:
    """Keep tweets diverse: avoid one promoter dominating after pagination."""
    counts: dict[str, int] = {}
    out: list[dict[str, Any]] = []
    for r in rows:
        uid = str(r.get("user") or "")
        n = counts.get(uid, 0)
        if n >= cap:
            continue
        counts[uid] = n + 1
        out.append(r)
    return out


def fetch_search_page(
    *,
    query: str,
    section: str | None,
    min_retweets: int,
    min_likes: int,
    min_replies: int | None,
    limit: int,
    start_date: str | None,
    end_date: str | None,
    language: str | None,
    continuation_token: str | None,
) -> dict[str, Any]:
    key = os.environ.get("RAPIDAPI_KEY", "").strip()
    if not key:
        raise SystemExit(
            "Missing RAPIDAPI_KEY. Set it in the environment:\n"
            '  export RAPIDAPI_KEY="your-key-here"'
        )

    params: dict[str, Any] = {
        "query": query,
        "min_retweets": min_retweets,
        "min_likes": min_likes,
        "limit": limit,
    }
    if section:
        params["section"] = section
    if min_replies is not None:
        params["min_replies"] = min_replies
    if start_date:
        params["start_date"] = start_date
    if end_date:
        params["end_date"] = end_date
    if language:
        params["language"] = language
    if continuation_token:
        params["continuation_token"] = continuation_token

    qs = urllib.parse.urlencode(params, doseq=True)
    url = f"{BASE_URL}?{qs}"

    req = urllib.request.Request(
        url,
        headers={
            "X-RapidAPI-Key": key,
            "X-RapidAPI-Host": "twitter154.p.rapidapi.com",
            "Accept": "application/json",
        },
        method="GET",
    )

    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            body = resp.read().decode("utf-8", errors="replace")
    except urllib.error.HTTPError as e:
        err_body = e.read().decode("utf-8", errors="replace")
        raise SystemExit(f"HTTP {e.code}: {e.reason}\n{err_body}") from e
    except urllib.error.URLError as e:
        raise SystemExit(f"Request failed: {e.reason}") from e

    try:
        return json.loads(body)
    except json.JSONDecodeError as e:
        raise SystemExit(f"Invalid JSON response: {e}\n---\n{body[:2000]}") from e


def _fenced(content: str) -> str:
    """Wrap text in a markdown fence; avoid breaking if tweet contains ```."""
    if "```" in content:
        return f"~~~text\n{content}\n~~~\n"
    return f"```text\n{content}\n```\n"


def render_markdown(
    *,
    out_obj: dict[str, Any],
    results: list[dict[str, Any]],
) -> str:
    """Human/agent-readable Markdown snapshot."""
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    filters = out_obj.get("filters") or {}
    lines: list[str] = [
        "# X search snapshot",
        "",
        f"- **Generated:** {now}",
        f"- **Pages fetched:** {out_obj.get('pages_fetched', 0)}",
        f"- **Tweets listed:** {len(results)}",
        "",
        "## Filters",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ]
    for key in sorted(filters.keys()):
        val = filters[key]
        if val is None:
            continue
        cell = str(val).replace("|", "\\|").replace("\n", " ")
        lines.append(f"| `{key}` | {cell} |")
    ct = out_obj.get("continuation_token")
    lines.extend(
        [
            "",
            "## Tweets",
            "",
        ]
    )
    if not results:
        lines.append("_No tweets in this run._\n")
    for i, r in enumerate(results, start=1):
        user = r.get("user") or "(unknown)"
        created = r.get("created_at") or "—"
        fav = r.get("favorite_count")
        rts = r.get("retweet_count")
        text = r.get("text") or ""
        lines.append(f"### {i}. @{user}")
        lines.append("")
        lines.append(f"- **When:** {created}")
        lines.append(f"- **Likes:** {fav} · **Retweets:** {rts}")
        lines.append("")
        lines.append(_fenced(text))
        lines.append("")
    if ct:
        lines.append("---")
        lines.append("")
        lines.append(f"_More results available (`continuation_token` present; see JSON)._")
        lines.append("")
    return "\n".join(lines)


def main() -> None:
    p = argparse.ArgumentParser(description="RapidAPI twitter154 search -> JSON / optional Markdown")
    p.add_argument("--query", default=DEFAULT_QUERY)
    p.add_argument(
        "--section",
        default="top",
        choices=("top", "latest"),
        help="top = surfaced posts; latest = chronological (often noisier)",
    )
    p.add_argument(
        "--min-retweets",
        type=int,
        default=10,
        help="Floors viral/spam replies; raise for stricter (e.g. 25–100)",
    )
    p.add_argument(
        "--min-likes",
        type=int,
        default=50,
        help="Primary quality gate; raise for quieter niches",
    )
    p.add_argument(
        "--min-replies",
        type=int,
        default=5,
        help="Prefer threads with discussion (set 0 to disable floor)",
    )
    p.add_argument("--limit", type=int, default=15, help="Per request, 1..20")
    p.add_argument(
        "--start-date",
        dest="start_date",
        default=None,
        help="YYYY-MM-DD lower bound (overrides --recency-days if set)",
    )
    p.add_argument("--end-date", dest="end_date", default=None, help="YYYY-MM-DD upper bound")
    p.add_argument(
        "--recency-days",
        type=int,
        default=14,
        help="Used as start_date = today−N (UTC); ignored if --start-date set",
    )
    p.add_argument(
        "--no-recency-filter",
        action="store_true",
        help="Do not send start_date (full index range supported by API)",
    )
    p.add_argument("--language", default="en")
    p.add_argument(
        "--max-pages",
        type=int,
        default=3,
        help="Follow continuation_token until empty or this many requests",
    )
    p.add_argument(
        "--max-per-user",
        type=int,
        default=2,
        help="Keep at most N tweets per screen_name in final output (0 = no limit)",
    )
    p.add_argument("--out", "-o", type=Path, default=DEFAULT_JSON_OUT)
    p.add_argument(
        "--markdown",
        "-m",
        action="store_true",
        help="Also write Markdown next to JSON (same path as --out with .md extension)",
    )
    p.add_argument(
        "--md-out",
        type=Path,
        default=None,
        metavar="PATH",
        help="Write Markdown to this path (--markdown not required)",
    )
    args = p.parse_args()

    lim = max(1, min(20, args.limit))
    max_pages = max(1, args.max_pages)

    start_date: str | None
    if args.start_date:
        start_date = args.start_date
    elif args.no_recency_filter:
        start_date = None
    else:
        day = datetime.now(timezone.utc).date() - timedelta(days=max(1, args.recency_days))
        start_date = day.isoformat()

    min_replies = args.min_replies
    if min_replies is not None and min_replies <= 0:
        min_replies = None

    seen: set[str] = set()
    results_out: list[dict[str, Any]] = []
    token: str | None = None
    pages_done = 0

    while pages_done < max_pages:
        payload = fetch_search_page(
            query=args.query,
            section=args.section or None,
            min_retweets=args.min_retweets,
            min_likes=args.min_likes,
            min_replies=min_replies,
            limit=lim,
            start_date=start_date or None,
            end_date=args.end_date or None,
            language=args.language or None,
            continuation_token=token,
        )
        batch = payload.get("results") or []
        if not isinstance(batch, list):
            break
        for t in batch:
            if not isinstance(t, dict):
                continue
            tid = t.get("tweet_id")
            key_id = str(tid) if tid is not None else None
            if key_id:
                if key_id in seen:
                    continue
                seen.add(key_id)
            row = _simplify_tweet(t)
            results_out.append(row)

        pages_done += 1
        token = payload.get("continuation_token") if isinstance(payload, dict) else None
        if not token:
            break
        if isinstance(token, str) and not token.strip():
            token = None
            break

    results_final = (
        _apply_max_per_user(results_out, args.max_per_user)
        if args.max_per_user > 0
        else results_out
    )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    out_obj = {
        "continuation_token": token,
        "pages_fetched": pages_done,
        "filters": {
            "query": args.query,
            "section": args.section,
            "min_retweets": args.min_retweets,
            "min_likes": args.min_likes,
            "min_replies": min_replies,
            "limit": lim,
            "start_date": start_date,
            "end_date": args.end_date,
            "language": args.language,
            "recency_days": None if args.start_date or args.no_recency_filter else args.recency_days,
            "max_per_user": args.max_per_user if args.max_per_user > 0 else None,
        },
        "results": results_final,
    }
    with args.out.open("w", encoding="utf-8") as f:
        json.dump(out_obj, f, ensure_ascii=False, indent=2)

    print(
        f"Wrote -> {args.out.resolve()} "
        f"({len(results_final)} tweet(s) after caps, {len(results_out)} before, {pages_done} page(s))"
    )
    if token:
        print(f"More pages available (next continuation_token saved in JSON)")

    md_path: Path | None = args.md_out
    if md_path is None and args.markdown:
        md_path = args.out.with_suffix(".md")
    if md_path is not None:
        md_path = md_path.resolve()
        md_path.parent.mkdir(parents=True, exist_ok=True)
        md_body = render_markdown(out_obj=out_obj, results=results_final)
        md_path.write_text(md_body, encoding="utf-8")
        print(f"Wrote MD -> {md_path}")


if __name__ == "__main__":
    main()
