#!/usr/bin/env python3
"""
Stage 4 — Sentiment Analysis Worker.

Đọc mapped_events (hoặc fallback clean_events), chạy NLP sentiment model,
ghi kết quả vào sentiment_events. Hỗ trợ aggregate theo coin_id + timeframe.

Usage:
    python -m playground.sentiment.run --limit 100
    python -m playground.sentiment.run --limit 1000 --source twitter
    python -m playground.sentiment.run --aggregate --timeframe 1h
    python -m playground.sentiment.run --limit 500 --aggregate --timeframe 1h
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

# Thêm sentiment dir vào path để import lib
_SENTIMENT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(_SENTIMENT_DIR))

from lib.utils import setup_logging  # noqa: E402

logger = logging.getLogger(__name__)


def run_batch(
    *,
    limit: int = 100,
    source: str | None = None,
    dry_run: bool = False,
) -> dict[str, int]:
    """Chạy sentiment scoring batch.

    Returns:
        dict với processed, skipped, errors, inserted.
    """
    from tqdm import tqdm

    from lib.config import (
        mapped_collection,
        sentiment_collection,
        sentiment_max_length,
        sentiment_model,
        use_rule_fallback,
    )
    from lib.mongo import (
        already_scored,
        ensure_indexes,
        fetch_input_events,
        get_db,
        insert_sentiment,
    )
    from lib.schema import build_sentiment_event
    from lib.scorer import SentimentScorer, try_alpha_vantage_sentiment

    db = get_db()
    ensure_indexes(db)

    logger.info("Connected to MongoDB: %s", db.name)

    # Lấy input events
    input_col, events = fetch_input_events(db, limit=limit, source=source)
    logger.info("Input collection: %s (%d events)", input_col.name, len(events))
    logger.info("Output collection: %s", sentiment_collection())

    if not events:
        logger.info("Không có event mới để xử lý.")
        return {"processed": 0, "skipped": 0, "errors": 0, "inserted": 0}

    # Init scorer
    model_name = sentiment_model()
    max_length = sentiment_max_length()
    rule_fallback = use_rule_fallback()
    logger.info("Loading sentiment model: %s", model_name)

    scorer = SentimentScorer(
        model_name=model_name,
        max_length=max_length,
        use_rule_fallback=rule_fallback,
    )

    sent_col = db[sentiment_collection()]

    stats = {"processed": 0, "skipped": 0, "errors": 0, "inserted": 0}

    for event in tqdm(events, desc="Processing", unit="event"):
        try:
            # Check đã score chưa
            if already_scored(sent_col, event):
                stats["skipped"] += 1
                continue

            text = event.get("clean_text") or event.get("raw_text", "")
            if not text.strip():
                stats["skipped"] += 1
                continue

            # Ưu tiên Alpha Vantage score nếu có
            result = try_alpha_vantage_sentiment(event)

            if result is None:
                # Chạy model NLP
                result = scorer.score_text(text)

            if dry_run:
                stats["processed"] += 1
                continue

            # Build document và insert
            doc = build_sentiment_event(event, result)
            if insert_sentiment(sent_col, doc):
                stats["inserted"] += 1
            else:
                stats["skipped"] += 1  # duplicate

            stats["processed"] += 1

        except Exception as exc:
            logger.warning(
                "Lỗi xử lý event %s: %s",
                event.get("event_id", "?"),
                exc,
            )
            stats["errors"] += 1

    logger.info(
        "processed=%d skipped=%d errors=%d inserted=%d",
        stats["processed"],
        stats["skipped"],
        stats["errors"],
        stats["inserted"],
    )
    return stats


def run_aggregate(*, timeframe: str = "1h", coin_id: str | None = None) -> int:
    """Chạy aggregate sentiment theo timeframe."""
    from lib.aggregate import aggregate_sentiment
    from lib.mongo import ensure_indexes, get_db

    db = get_db()
    ensure_indexes(db)

    logger.info("Aggregating sentiment (timeframe=%s, coin=%s)...", timeframe, coin_id or "ALL")
    count = aggregate_sentiment(db, timeframe=timeframe, coin_id=coin_id)
    logger.info("Aggregate hoàn tất: %d documents upserted.", count)
    return count


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Stage 4 — Sentiment Analysis Worker",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ví dụ:
  python -m playground.sentiment.run --limit 100
  python -m playground.sentiment.run --limit 1000 --source twitter
  python -m playground.sentiment.run --aggregate --timeframe 1h
  python -m playground.sentiment.run --limit 500 --aggregate --timeframe 1h --coin BTC
        """,
    )

    # Batch args
    parser.add_argument(
        "--limit",
        type=int,
        default=100,
        help="Số lượng events tối đa để xử lý (default: 100)",
    )
    parser.add_argument(
        "--source",
        type=str,
        default=None,
        help="Lọc theo source: twitter, news, reddit, ...",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Chạy thử, không ghi vào MongoDB",
    )

    # Aggregate args
    parser.add_argument(
        "--aggregate",
        action="store_true",
        help="Chạy aggregate sentiment sau khi batch",
    )
    parser.add_argument(
        "--timeframe",
        type=str,
        default="1h",
        choices=["15m", "30m", "1h", "4h", "1d"],
        help="Timeframe cho aggregate (default: 1h)",
    )
    parser.add_argument(
        "--coin",
        type=str,
        default=None,
        help="Lọc aggregate theo coin_id (VD: BTC, ETH)",
    )

    # General
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Chỉ hiện lỗi",
    )
    parser.add_argument(
        "--aggregate-only",
        action="store_true",
        help="Chỉ chạy aggregate, bỏ qua batch scoring",
    )

    args = parser.parse_args()

    setup_logging(level=logging.WARNING if args.quiet else logging.INFO)

    # Batch scoring
    if not args.aggregate_only:
        run_batch(limit=args.limit, source=args.source, dry_run=args.dry_run)

    # Aggregate
    if args.aggregate or args.aggregate_only:
        run_aggregate(timeframe=args.timeframe, coin_id=args.coin)


if __name__ == "__main__":
    main()
