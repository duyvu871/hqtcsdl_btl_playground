#!/usr/bin/env python3
"""
Pipeline Stage 2 — Lọc spam/noise từ raw events MongoDB (ingest Stage 1).

Cascade:
  L1 heuristic → L2 SimHash → L3 FastText (nếu có model)

  cd playground/filter
  uv sync
  uv run python run.py --dry-run
  uv run python run.py --limit 500
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.cascade import FilterStats, default_ml_classifier, run_cascade
from lib.export import default_export_path, export_evaluation_report
from lib.heuristic import HeuristicConfig
from lib.mongo import (
    build_clean_doc,
    build_dropped_doc,
    ensure_indexes,
    fetch_unprocessed_raw,
    get_clean_collection,
    get_dropped_collection,
    get_raw_collection,
    insert_clean,
    insert_dropped,
)
from lib.progress import Progress


def _print_stats(stats: FilterStats, *, ml_available: bool) -> None:
    dropped = stats.dropped_l1 + stats.dropped_l2 + stats.dropped_l3
    pct_pass = (100.0 * stats.passed / stats.total) if stats.total else 0.0
    pct_drop = (100.0 * dropped / stats.total) if stats.total else 0.0

    print(f"\n=== Kết quả cascade ===")
    print(f"  Tổng xử lý:     {stats.total}")
    print(f"  PASS:           {stats.passed} ({pct_pass:.1f}%)")
    print(f"  DROP:           {dropped} ({pct_drop:.1f}%)")
    print(f"    L1 heuristic: {stats.dropped_l1}")
    print(f"    L2 SimHash:   {stats.dropped_l2}")
    print(f"    L3 FastText:  {stats.dropped_l3}")
    if not ml_available:
        print("  (L3 bỏ qua — chưa có spam_model.bin; train tại playground/finetune/fasttext)")

    if stats.by_reason:
        print("\n  Chi tiết DROP:")
        for key in sorted(stats.by_reason):
            print(f"    {key}: {stats.by_reason[key]}")


def _print_samples(
    passed: list[tuple[dict[str, Any], Any]],
    dropped: list[tuple[dict[str, Any], Any]],
) -> None:
    if passed:
        raw, outcome = passed[0]
        print("\nMẫu PASS:")
        print(f"  event_id: {raw.get('event_id')}")
        print(f"  source:   {raw.get('source')}")
        text = outcome.clean_text
        if len(text) > 100:
            text = text[:100] + "..."
        print(f"  text:     {text}")

    if dropped:
        raw, outcome = dropped[0]
        print("\nMẫu DROP:")
        print(f"  event_id: {raw.get('event_id')}")
        print(f"  stage:    {outcome.stage}")
        print(f"  reason:   {outcome.reason}")


def _heuristic_from_args(args: argparse.Namespace) -> HeuristicConfig:
    return HeuristicConfig(
        min_likes=args.min_likes,
        max_per_author=args.max_per_author,
        min_engagement_ratio=args.min_engagement_ratio,
        max_engagement_ratio=args.max_engagement_ratio,
        skip_news=not args.filter_news,
    )


def cmd_run(args: argparse.Namespace) -> None:
    progress = Progress(quiet=args.quiet)
    progress.log("=== Stage 2 — Spam / Noise Filter ===")

    raw_col = get_raw_collection()
    clean_col = get_clean_collection()
    dropped_col = get_dropped_collection() if args.save_dropped else None

    progress.log("Đang đọc raw events chưa xử lý...")
    events = fetch_unprocessed_raw(
        raw_col,
        clean_col,
        limit=args.limit,
        source=args.source,
        since_ts=args.since,
    )
    progress.log(f"Tìm thấy {len(events)} event(s) cần lọc.")

    if not events:
        progress.log("Không có event mới. Chạy playground/ingest trước hoặc tăng --limit.")
        return

    ml = default_ml_classifier()
    if args.no_ml:
        ml = None
    elif ml and not ml.available:
        progress.log(f"FastText model chưa có tại {ml.config.model_path}")

    heuristic = _heuristic_from_args(args)
    stats = FilterStats()
    passed_pairs, dropped_pairs = run_cascade(
        events,
        heuristic=heuristic,
        ml=ml,
        stats=stats,
    )

    _print_stats(stats, ml_available=bool(ml and ml.available))
    if args.verbose or args.dry_run:
        _print_samples(passed_pairs, dropped_pairs)

    if args.export_sheet is not None:
        out_path = (
            default_export_path()
            if args.export_sheet == "auto"
            else Path(args.export_sheet)
        )
        run_meta = {
            "limit": args.limit,
            "source": args.source or "all",
            "dry_run": args.dry_run,
            "no_ml": args.no_ml,
            "min_likes": args.min_likes,
            "max_per_author": args.max_per_author or "off",
            "filter_news": args.filter_news,
        }
        saved = export_evaluation_report(
            passed=passed_pairs,
            dropped=dropped_pairs,
            stats=stats,
            path=out_path,
            ml_available=bool(ml and ml.available),
            run_meta=run_meta,
        )
        progress.log(
            f"Đã xuất báo cáo ({stats.total} events: "
            f"{stats.passed} PASS, {stats.dropped_l1 + stats.dropped_l2 + stats.dropped_l3} DROP) → {saved}"
        )

    if args.dry_run:
        progress.log("\n--dry-run: không ghi MongoDB.")
        return

    progress.log("\nĐang ghi MongoDB...")
    ensure_indexes(clean_col, dropped_col)

    clean_docs = [
        build_clean_doc(raw, filter_meta={"stage": o.stage, **o.meta, "clean_text": o.clean_text})
        for raw, o in passed_pairs
    ]
    ins, skip = insert_clean(clean_col, clean_docs, progress=progress)
    progress.log(f"clean_events: insert {ins}, bỏ qua trùng {skip}.")

    if dropped_col is not None and dropped_pairs:
        dropped_docs = [
            build_dropped_doc(
                raw,
                reason=o.reason or "unknown",
                stage=o.stage,
                filter_meta=o.meta,
            )
            for raw, o in dropped_pairs
        ]
        d_ins, d_skip = insert_dropped(dropped_col, dropped_docs, progress=progress)
        progress.log(f"dropped_events: insert {d_ins}, bỏ qua trùng {d_skip}.")


def cmd_stats(args: argparse.Namespace) -> None:
    raw_col = get_raw_collection()
    clean_col = get_clean_collection()
    dropped_col = get_dropped_collection()

    raw_count = raw_col.count_documents({})
    clean_count = clean_col.count_documents({})
    dropped_count = dropped_col.count_documents({})
    pending = len(
        fetch_unprocessed_raw(raw_col, clean_col, limit=100_000, source=args.source)
    )

    print(json.dumps(
        {
            "raw_events": raw_count,
            "clean_events": clean_count,
            "dropped_events": dropped_count,
            "pending_unprocessed": pending,
        },
        indent=2,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Stage 2 — spam/noise filter")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "stats"),
        help="run (mặc định) hoặc stats",
    )
    parser.add_argument("--source", choices=("twitter", "reddit", "news"), help="Chỉ xử lý nguồn")
    parser.add_argument("-q", "--quiet", action="store_true", help="Ít log")
    parser.add_argument("--limit", type=int, default=1000, help="Số event tối đa mỗi lần chạy")
    parser.add_argument("--since", type=int, help="Chỉ lấy raw có timestamp >= (Unix giây)")
    parser.add_argument("--dry-run", action="store_true", help="Chỉ in stats, không ghi DB")
    parser.add_argument("-v", "--verbose", action="store_true", help="In mẫu PASS/DROP")
    parser.add_argument("--save-dropped", action="store_true", help="Ghi DROP vào dropped_events")
    parser.add_argument(
        "--export-sheet",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="Xuất báo cáo đánh giá Excel (.xlsx): summary + all + passed + dropped",
    )
    parser.add_argument("--no-ml", action="store_true", help="Tắt L3 FastText")
    parser.add_argument("--min-likes", type=int, default=0, help="L1: ngưỡng likes tối thiểu")
    parser.add_argument(
        "--max-per-author",
        type=int,
        default=0,
        help="L1: tối đa event/author trong batch (0=tắt)",
    )
    parser.add_argument(
        "--min-engagement-ratio",
        type=float,
        default=0.0,
        help="L1: (likes+RT+comments)/followers tối thiểu",
    )
    parser.add_argument(
        "--max-engagement-ratio",
        type=float,
        default=0.0,
        help="L1: ratio tối đa — phát hiện shill (0=tắt)",
    )
    parser.add_argument(
        "--filter-news",
        action="store_true",
        help="Áp dụng L1/L3 cho news (mặc định news chỉ check text rỗng)",
    )

    args = parser.parse_args()
    func = cmd_stats if args.command == "stats" else cmd_run

    try:
        func(args)
    except ValueError as exc:
        print(f"Lỗi cấu hình: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
