#!/usr/bin/env python3
"""Stage 5 — Influence Weighting.

Luồng chuẩn:
    sentiment_events  ->  weighted_events  ->  influence_aggregates

Module này chỉ làm việc trong folder `playground/influence` và MongoDB collections
của Step 5. Không sửa code/collection của Stage 4 hoặc Stage 6.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_INFLUENCE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_INFLUENCE_DIR))

from lib.aggregate import TIMEFRAME_SECONDS, aggregate_weighted_events  # noqa: E402
from lib.config import (  # noqa: E402
    influence_agg_collection,
    sentiment_collection,
    weighted_collection,
)
from lib.mongo import (  # noqa: E402
    build_weighted_documents,
    collection_stats,
    ensure_indexes,
    fetch_sentiment_events,
    get_db,
    insert_weighted_events,
)
from lib.progress import Progress  # noqa: E402


def run_process(args: argparse.Namespace, progress: Progress) -> dict[str, int]:
    db = get_db()
    ensure_indexes(db)

    sent_col = db[sentiment_collection()]
    weighted_col = db[weighted_collection()]

    events = fetch_sentiment_events(
        sent_col,
        weighted_col,
        limit=args.limit,
        source=args.source,
        coin_id=args.coin,
        since_ts=args.since_ts,
        reprocess=args.reprocess,
    )

    progress.log(
        f"[cyan]Input:[/cyan] {sentiment_collection()} | "
        f"[cyan]Output:[/cyan] {weighted_collection()} | events={len(events)}"
    )

    docs = build_weighted_documents(events)

    if args.verbose or args.dry_run:
        for doc in docs[: min(10, len(docs))]:
            progress.log("-" * 90)
            progress.log(
                f"coin={doc.get('coin_id')} source={doc.get('source')} "
                f"author={doc.get('author_id')} sentiment={doc.get('sentiment_score')} "
                f"influence={doc.get('influence_weight')} "
                f"weighted={doc.get('weighted_sentiment')}"
            )
            progress.log(f"detail={doc.get('influence')}")
            text = str(doc.get("clean_text") or "")
            if text:
                progress.log(text[:250])

    if args.dry_run:
        progress.log(f"[yellow][DRY-RUN][/yellow] Would write {len(docs)} weighted events.")
        return {"processed": len(events), "inserted": 0, "skipped": 0}

    inserted, skipped = insert_weighted_events(
        weighted_col,
        docs,
        replace=args.reprocess,
    )
    progress.log(f"[green]Done.[/green] processed={len(events)} inserted={inserted} skipped={skipped}")
    return {"processed": len(events), "inserted": inserted, "skipped": skipped}


def run_aggregate(args: argparse.Namespace, progress: Progress) -> int:
    db = get_db()
    ensure_indexes(db)

    weighted_col = db[weighted_collection()]
    agg_col = db[influence_agg_collection()]

    count = aggregate_weighted_events(
        weighted_col,
        agg_col,
        timeframe=args.timeframe,
        coin_id=args.coin,
        since_ts=args.since_ts,
    )
    progress.log(
        f"[green]Aggregate done.[/green] {weighted_collection()} -> "
        f"{influence_agg_collection()} | upserted={count}"
    )
    return count


def run_stats(progress: Progress) -> dict[str, int]:
    db = get_db()
    ensure_indexes(db)
    stats = collection_stats(db)
    for name, count in stats.items():
        progress.log(f"{name}: {count}")
    return stats


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Stage 5 — Influence Weighting",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  uv run python run.py --dry-run -v --limit 20
  uv run python run.py --limit 500
  uv run python run.py --coin BTC --limit 200
  uv run python run.py --limit 500 --aggregate --timeframe 1h
  uv run python run.py --aggregate-only --timeframe 1h
  uv run python run.py --stats
        """,
    )

    parser.add_argument("--limit", type=int, default=100, help="Số sentiment_events tối đa để xử lý")
    parser.add_argument("--source", type=str, default=None, help="Lọc theo source: twitter, reddit, news")
    parser.add_argument("--coin", type=str, default=None, help="Lọc theo coin_id, VD: BTC")
    parser.add_argument("--since-ts", type=int, default=None, help="Chỉ xử lý event từ timestamp này")
    parser.add_argument("--dry-run", action="store_true", help="Chạy thử, không ghi MongoDB")
    parser.add_argument("--reprocess", action="store_true", help="Tính lại event đã xử lý và upsert output")
    parser.add_argument("-v", "--verbose", action="store_true", help="In sample output chi tiết")
    parser.add_argument("--quiet", action="store_true", help="Chỉ in tối thiểu")

    parser.add_argument("--aggregate", action="store_true", help="Aggregate sau khi process")
    parser.add_argument("--aggregate-only", action="store_true", help="Chỉ aggregate, không process")
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1h",
        choices=list(TIMEFRAME_SECONDS.keys()),
        help="Timeframe aggregate cho output Stage 6",
    )
    parser.add_argument("--stats", action="store_true", help="In số lượng documents trong các collection Step 5")

    return parser.parse_args()


def main() -> None:
    args = parse_args()
    progress = Progress(quiet=args.quiet)

    if args.stats:
        run_stats(progress)
        return

    if args.aggregate_only:
        run_aggregate(args, progress)
        return

    run_process(args, progress)

    if args.aggregate and not args.dry_run:
        run_aggregate(args, progress)


if __name__ == "__main__":
    main()
