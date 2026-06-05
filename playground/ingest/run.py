#!/usr/bin/env python3
"""
Pipeline Stage 1 — Ingest đa nguồn → lưu MongoDB Atlas.

  cd playground/ingest
  cp .env.example .env
  uv sync
  uv run python run.py twitter
  uv run python run.py news-av
  uv run python run.py news-yahoo --symbol ETH-USD
  uv run python run.py reddit --subreddit Bitcoin
  uv run python run.py all
"""

from __future__ import annotations

import argparse
import sys
from typing import Any, Callable

from lib.collectors import (
    DEFAULT_QUERY,
    collect_news_av_events,
    collect_news_yahoo_events,
    collect_reddit_browser_events,
    collect_reddit_events,
    collect_twitter_events,
    save_reddit_browser_session,
)
from lib.config import alpha_vantage_api_key, rapidapi_key
from lib.mongo import ensure_indexes, get_collection, insert_events
from lib.progress import Progress


def _progress(args: argparse.Namespace) -> Progress:
    return Progress(quiet=getattr(args, "quiet", False))


def _print_sample(events: list[dict[str, Any]]) -> None:
    if not events:
        return
    sample = events[0]
    print("Mẫu document đầu tiên:")
    for key in ("event_id", "source", "external_id", "author_id", "timestamp", "raw_text"):
        val = sample.get(key)
        if key == "raw_text" and isinstance(val, str) and len(val) > 120:
            val = val[:120] + "..."
        print(f"  {key}: {val}")


def _persist(
    events: list[dict[str, Any]],
    *,
    dry_run: bool,
    progress: Progress,
) -> None:
    progress.log(f"Thu thập xong: {len(events)} raw event(s).")
    if dry_run:
        _print_sample(events)
        return

    progress.log("Đang kết nối MongoDB Atlas...")
    collection = get_collection()
    progress.log("Đang tạo/kiểm tra index...")
    ensure_indexes(collection)
    inserted, skipped = insert_events(collection, events, progress=progress)
    progress.log(f"Hoàn tất: insert {inserted}, bỏ qua trùng {skipped} → {collection.full_name}.")


def cmd_twitter(args: argparse.Namespace) -> None:
    progress = _progress(args)
    progress.log("=== Twitter / X (RapidAPI) ===")
    events = collect_twitter_events(
        query=args.query,
        max_pages=args.max_pages,
        limit_per_page=args.limit,
        min_likes=args.min_likes,
        min_retweets=args.min_retweets,
        recency_days=args.recency_days,
        progress=progress,
    )
    _persist(events, dry_run=args.dry_run, progress=progress)


def cmd_news_av(args: argparse.Namespace) -> None:
    progress = _progress(args)
    progress.log("=== Alpha Vantage NEWS_SENTIMENT ===")
    events = collect_news_av_events(
        tickers=args.tickers,
        days=args.days,
        limit=args.limit,
        topics=args.topics,
        progress=progress,
    )
    _persist(events, dry_run=args.dry_run, progress=progress)


def cmd_news_yahoo(args: argparse.Namespace) -> None:
    progress = _progress(args)
    progress.log(f"=== Yahoo Finance ({args.symbol}) ===")
    events = collect_news_yahoo_events(
        symbol=args.symbol,
        limit=args.limit,
        progress=progress,
    )
    _persist(events, dry_run=args.dry_run, progress=progress)


def cmd_reddit(args: argparse.Namespace) -> None:
    progress = _progress(args)

    if args.login:
        if not args.browser:
            raise RuntimeError("Cần --browser kèm --login để lưu session Reddit.")
        progress.log("=== Reddit browser — đăng nhập & lưu session ===")
        save_reddit_browser_session(progress=progress)
        return

    mode = "browser" if args.browser else "api"
    progress.log(f"=== Reddit r/{args.subreddit} ({args.listing}, {mode}) ===")

    collect = collect_reddit_browser_events if args.browser else collect_reddit_events
    events = collect(
        subreddit=args.subreddit,
        query=args.query,
        sort=args.sort,
        limit=args.limit,
        listing=args.listing,
        progress=progress,
    )
    _persist(events, dry_run=args.dry_run, progress=progress)


def cmd_all(args: argparse.Namespace) -> None:
    progress = _progress(args)
    progress.log("=== Ingest tất cả nguồn ===")
    collectors: list[tuple[str, Callable[[], list[dict[str, Any]]]]] = []

    try:
        rapidapi_key()
        collectors.append(
            (
                "twitter",
                lambda: collect_twitter_events(
                    query=args.query,
                    max_pages=args.max_pages,
                    limit_per_page=args.limit,
                    min_likes=args.min_likes,
                    min_retweets=args.min_retweets,
                    recency_days=args.recency_days,
                    progress=progress,
                ),
            )
        )
    except ValueError:
        progress.log("Bỏ qua twitter — thiếu RAPIDAPI_KEY.")

    try:
        alpha_vantage_api_key()
        collectors.append(
            (
                "news-av",
                lambda: collect_news_av_events(
                    tickers=args.tickers,
                    days=args.days,
                    limit=args.limit,
                    progress=progress,
                ),
            )
        )
    except ValueError:
        progress.log("Bỏ qua news-av — thiếu ALPHA_VANTAGE_API_KEY.")

    collectors.append(
        (
            "news-yahoo",
            lambda: collect_news_yahoo_events(
                symbol=args.symbol,
                limit=args.limit,
                progress=progress,
            ),
        )
    )

    if args.with_reddit:
        collectors.append(
            (
                "reddit",
                lambda: (
                    collect_reddit_browser_events
                    if args.reddit_browser
                    else collect_reddit_events
                )(
                    subreddit=args.subreddit,
                    query=args.query,
                    limit=args.limit,
                    listing="search",
                    progress=progress,
                ),
            )
        )
    else:
        progress.log("Bỏ qua reddit (mặc định). Thêm --with-reddit nếu cần.")

    all_events: list[dict[str, Any]] = []
    total = len(collectors)
    for i, (name, fn) in enumerate(collectors, start=1):
        progress.log(f"\n--- Nguồn {i}/{total}: {name} ---")
        try:
            batch = fn()
            progress.log(f"  → {len(batch)} event(s)")
            all_events.extend(batch)
        except (RuntimeError, OSError) as e:
            progress.log(f"  Lỗi: {e}")

    _persist(all_events, dry_run=args.dry_run, progress=progress)


def main() -> None:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument(
        "--dry-run",
        action="store_true",
        help="Chỉ fetch, không ghi DB",
    )
    common.add_argument(
        "--quiet",
        "-q",
        action="store_true",
        help="Tắt progress bar và log chi tiết",
    )

    parser = argparse.ArgumentParser(description="Ingest raw events đa nguồn vào MongoDB Atlas")
    sub = parser.add_subparsers(dest="cmd", required=True)

    p_tw = sub.add_parser("twitter", parents=[common], help="X/Twitter qua RapidAPI twitter154")
    p_tw.add_argument("--query", default=DEFAULT_QUERY)
    p_tw.add_argument("--max-pages", type=int, default=2)
    p_tw.add_argument("--limit", type=int, default=15, help="Tweet mỗi trang (1–20)")
    p_tw.add_argument("--min-likes", type=int, default=50)
    p_tw.add_argument("--min-retweets", type=int, default=10)
    p_tw.add_argument("--recency-days", type=int, default=14)
    p_tw.set_defaults(func=cmd_twitter)

    p_av = sub.add_parser("news-av", parents=[common], help="Tin crypto Alpha Vantage NEWS_SENTIMENT")
    p_av.add_argument("--tickers", default="CRYPTO:BTC,CRYPTO:ETH")
    p_av.add_argument("--days", type=int, default=7)
    p_av.add_argument("--limit", type=int, default=20)
    p_av.add_argument("--topics", default=None, help="Tuỳ chọn — cryptocurrency, blockchain, …")
    p_av.set_defaults(func=cmd_news_av)

    p_yf = sub.add_parser("news-yahoo", parents=[common], help="Tin gắn mã Yahoo (yfinance)")
    p_yf.add_argument("--symbol", default="BTC-USD")
    p_yf.add_argument("--limit", type=int, default=20)
    p_yf.set_defaults(func=cmd_news_yahoo)

    p_rd = sub.add_parser("reddit", parents=[common], help="Reddit public JSON API")
    p_rd.add_argument("--subreddit", default="cryptocurrency")
    p_rd.add_argument("--query", default="bitcoin OR ethereum OR BTC OR ETH")
    p_rd.add_argument("--sort", default="new", choices=("new", "relevance", "hot", "top"))
    p_rd.add_argument("--limit", type=int, default=25)
    p_rd.add_argument(
        "--listing",
        default="search",
        choices=("search", "hot", "new"),
        help="search = tìm trong sub; hot/new = feed subreddit",
    )
    p_rd.add_argument(
        "--browser",
        action="store_true",
        help="Dùng Playwright scrape old.reddit.com (không cần OAuth)",
    )
    p_rd.add_argument(
        "--login",
        action="store_true",
        help="Mở browser đăng nhập Reddit, lưu session (.reddit_session.json)",
    )
    p_rd.set_defaults(func=cmd_reddit)

    p_all = sub.add_parser(
        "all",
        parents=[common],
        help="Twitter + news-av + news-yahoo (không Reddit mặc định)",
    )
    p_all.add_argument("--query", default=DEFAULT_QUERY)
    p_all.add_argument("--max-pages", type=int, default=1)
    p_all.add_argument("--limit", type=int, default=10)
    p_all.add_argument("--min-likes", type=int, default=50)
    p_all.add_argument("--min-retweets", type=int, default=10)
    p_all.add_argument("--recency-days", type=int, default=14)
    p_all.add_argument("--tickers", default="CRYPTO:BTC,CRYPTO:ETH")
    p_all.add_argument("--days", type=int, default=7)
    p_all.add_argument("--symbol", default="BTC-USD")
    p_all.add_argument("--subreddit", default="cryptocurrency")
    p_all.add_argument(
        "--with-reddit",
        action="store_true",
        help="Thêm Reddit vào lệnh all (mặc định: bỏ qua)",
    )
    p_all.add_argument(
        "--reddit-browser",
        action="store_true",
        help="Khi --with-reddit: dùng Playwright thay OAuth API",
    )
    p_all.set_defaults(func=cmd_all)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    try:
        main()
    except (ValueError, RuntimeError) as e:
        print(f"Lỗi: {e}", file=sys.stderr)
        sys.exit(1)
