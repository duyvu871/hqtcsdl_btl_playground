#!/usr/bin/env python3
"""
Pipeline Stage 3 — NER & coin mapping.

Modes:
  hybrid    — rules trước; gọi LLM khi không có mention hoặc ambiguous
  validator — rules + LLM xác nhận/sửa mọi event
  full      — chỉ LLM

  cd playground/ner
  uv sync
  uv run python run.py --mode hybrid --input raw --dry-run --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from lib.config import ner_mode_default, openrouter_model
from lib.llm import OpenRouterNER
from lib.mongo import (
    build_mapped_docs,
    clear_mapped_for_events,
    ensure_indexes,
    fetch_input_events,
    fetch_unprocessed_input,
    get_clean_collection,
    get_mapped_collection,
    get_raw_collection,
    insert_mapped,
)
from lib.pipeline import NerMode, NerStats, map_event
from lib.progress import Progress
from lib.registry import CoinRegistry
from lib.run_log import (
    default_jsonl_path,
    default_log_path,
    log_event_record,
    log_summary,
    setup_run_logger,
)


def _print_stats(stats: NerStats, *, mode: str, model: str | None) -> None:
    print(f"\n=== Kết quả NER ({mode}) ===")
    if model:
        print(f"  Model:          {model}")
    print(f"  Events xử lý:   {stats.total}")
    print(f"  Có mention:     {stats.with_mentions}")
    print(f"  Không mention:  {stats.without_mentions}")
    print(f"  Fan-out rows:   {stats.fanout_records}")
    print(f"  LLM calls:      {stats.llm_calls}")
    if stats.llm_errors:
        print(f"  LLM errors:     {stats.llm_errors}")
    if stats.by_method:
        print("\n  Mentions theo method:")
        for key in sorted(stats.by_method):
            print(f"    {key}: {stats.by_method[key]}")


def _print_samples(results: list[tuple[dict[str, Any], Any, list]]) -> None:
    shown = 0
    for event, outcome, docs in results:
        if not outcome.mentions:
            continue
        print(f"\nMẫu map:")
        print(f"  parent_event_id: {event.get('event_id')}")
        print(f"  mode/notes:      {outcome.mode} / {outcome.notes}")
        print(f"  coins:           {[d['coin_id'] for d in docs]}")
        text = str(event.get('clean_text') or event.get('raw_text') or '')
        if len(text) > 120:
            text = text[:120] + "..."
        print(f"  text:            {text}")
        shown += 1
        if shown >= 3:
            break


def cmd_run(args: argparse.Namespace) -> None:
    progress = Progress(quiet=args.quiet)
    mode = NerMode.parse(args.mode or ner_mode_default())
    progress.log(f"=== Stage 3 — NER & Mapping ({mode.value}) ===")

    file_logger = None
    jsonl_path: Path | None = None
    log_path: Path | None = None
    if args.log_file is not None:
        log_path = default_log_path() if args.log_file == "auto" else Path(args.log_file)
        file_logger = setup_run_logger(log_path)
        jsonl_path = default_jsonl_path(log_path)
        progress.log(f"Log file: {log_path}")
        progress.log(f"JSONL:    {jsonl_path}")
        file_logger.info("=== START NER RUN mode=%s input=%s limit=%s ===", mode.value, args.input, args.limit)

    registry = CoinRegistry.load()
    source_col = get_raw_collection() if args.input == "raw" else get_clean_collection()
    mapped_col = get_mapped_collection()

    progress.log(f"Input collection: {source_col.name}")
    if args.reprocess:
        progress.log("--reprocess: xử lý lại mọi event (ghi đè mapped cũ).")
    events = fetch_input_events(
        source_col,
        mapped_col,
        limit=args.limit,
        source=args.source,
        since_ts=args.since,
        reprocess=args.reprocess,
    )
    progress.log(f"Tìm thấy {len(events)} event(s) cần map.")

    if not events:
        progress.log("Không có event mới.")
        return

    llm: OpenRouterNER | None = None
    if mode in (NerMode.FULL, NerMode.VALIDATOR) or mode == NerMode.HYBRID:
        try:
            llm = OpenRouterNER()
            progress.log(f"OpenRouter model: {openrouter_model()}")
        except ValueError as exc:
            if mode in (NerMode.FULL, NerMode.VALIDATOR):
                raise
            progress.log(f"LLM fallback tắt ({exc}) — chỉ dùng rules.")

    stats = NerStats()
    all_docs: list[dict[str, Any]] = []
    trace: list[tuple[dict[str, Any], Any, list]] = []

    for i, event in enumerate(events, start=1):
        outcome = map_event(event, mode=mode, registry=registry, llm=llm)
        docs = build_mapped_docs(event, outcome.mentions, outcome)
        stats.record(outcome, fanout_count=len(docs))
        all_docs.extend(docs)
        trace.append((event, outcome, docs))
        if log_path is not None:
            log_event_record(event=event, outcome=outcome, docs=docs, jsonl_path=jsonl_path)
        if progress and len(events) > 1:
            progress.bar(i, len(events), prefix="NER: ")

    _print_stats(stats, mode=mode.value, model=openrouter_model() if llm else None)
    if file_logger and log_path:
        log_summary(
            file_logger,
            stats=stats,
            mode=mode.value,
            model=openrouter_model() if llm else None,
            log_path=log_path,
        )
        progress.log(f"Đã ghi log → {log_path}")
        if jsonl_path:
            progress.log(f"Đã ghi JSONL → {jsonl_path}")
    if args.verbose or args.dry_run:
        _print_samples(trace)

    if args.dry_run:
        progress.log("\n--dry-run: không ghi MongoDB.")
        return

    if not all_docs:
        progress.log("Không có mapped record để ghi.")
        return

    if args.reprocess:
        event_ids = [str(e.get("event_id")) for e in events if e.get("event_id")]
        deleted = clear_mapped_for_events(mapped_col, event_ids)
        progress.log(f"Đã xóa {deleted} mapped record(s) cũ trước khi ghi lại.")

    progress.log("\nĐang ghi MongoDB...")
    ensure_indexes(mapped_col)
    ins, skip = insert_mapped(mapped_col, all_docs, progress=progress)
    progress.log(f"mapped_events: insert {ins}, bỏ qua trùng {skip}.")


def cmd_stats(args: argparse.Namespace) -> None:
    raw_col = get_raw_collection()
    clean_col = get_clean_collection()
    mapped_col = get_mapped_collection()

    pending_raw = len(
        fetch_unprocessed_input(raw_col, mapped_col, limit=100_000, source=args.source)
    )
    pending_clean = len(
        fetch_unprocessed_input(clean_col, mapped_col, limit=100_000, source=args.source)
    )

    print(json.dumps(
        {
            "raw_events": raw_col.count_documents({}),
            "clean_events": clean_col.count_documents({}),
            "mapped_events": mapped_col.count_documents({}),
            "pending_from_raw": pending_raw,
            "pending_from_clean": pending_clean,
        },
        indent=2,
    ))


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline Stage 3 — NER & coin mapping")
    parser.add_argument(
        "command",
        nargs="?",
        default="run",
        choices=("run", "stats"),
        help="run (mặc định) hoặc stats",
    )
    parser.add_argument(
        "--mode",
        choices=("hybrid", "validator", "full"),
        help="hybrid | validator | full (mặc định từ NER_MODE trong .env)",
    )
    parser.add_argument(
        "--input",
        choices=("clean", "raw"),
        default="clean",
        help="Đọc từ clean_events (mặc định) hoặc raw_events",
    )
    parser.add_argument("--source", choices=("twitter", "reddit", "news"), help="Chỉ xử lý nguồn")
    parser.add_argument("-q", "--quiet", action="store_true", help="Ít log")
    parser.add_argument("--limit", type=int, default=100, help="Số event tối đa mỗi lần chạy")
    parser.add_argument("--since", type=int, help="Chỉ lấy event có timestamp >= (Unix giây)")
    parser.add_argument("--dry-run", action="store_true", help="Không ghi MongoDB")
    parser.add_argument("-v", "--verbose", action="store_true", help="In mẫu map")
    parser.add_argument(
        "--log-file",
        nargs="?",
        const="auto",
        metavar="PATH",
        help="Ghi log chi tiết ra file (.log + .jsonl). Mặc định logs/ner_run_<ts>.log",
    )
    parser.add_argument(
        "--reprocess",
        action="store_true",
        help="Xử lý lại toàn bộ event (kể cả đã map), ghi đè mapped cũ",
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
