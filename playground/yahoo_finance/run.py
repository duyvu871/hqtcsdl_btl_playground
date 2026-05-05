#!/usr/bin/env python3
"""
Playground Yahoo Finance qua thư viện `yfinance`: stdout + JSON + Markdown.

  pip install -r requirements.txt

Examples (crypto — Yahoo ticker dạng ``BTC-USD``, ``ETH-USD``):

  python run.py fast-info --symbol BTC-USD
  python run.py history --symbol BTC-USD --period 7d --interval 1h
  python run.py info --symbol BTC-USD
  python run.py news --symbol ETH-USD
  python run.py ticker --symbols BTC-USD ETH-USD SOL-USD --period 5d
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

try:
    import yfinance as yf
except ImportError:
    print(
        "Chưa cài yfinance. Chạy:\n"
        "  pip install -r requirements.txt\n"
        "(trong thư mục playground/yahoo_finance)",
        file=sys.stderr,
    )
    sys.exit(1)

from yf_helpers import dataframe_to_records, json_sanitize, pretty_snippet, render_markdown

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = _SCRIPT_DIR / "yahoo_finance_response.json"
DEFAULT_MD_OUT = _SCRIPT_DIR / "yahoo_finance_response.md"

_io_parent = argparse.ArgumentParser(add_help=False)
_io_parent.add_argument("--json-out", type=Path, default=DEFAULT_JSON_OUT, metavar="PATH")
_io_parent.add_argument("--md-out", type=Path, default=DEFAULT_MD_OUT, metavar="PATH")
_io_parent.add_argument("--no-save", action="store_true", help="Chỉ in stdout")


def _write_outputs(
    *,
    args: argparse.Namespace,
    cmd: str,
    descriptor: str,
    request_params: dict[str, Any],
    response: dict[str, Any] | list[Any],
) -> None:
    if args.no_save:
        return

    payload = {
        "command": cmd,
        "source": "yfinance (Yahoo Finance – API không chính thức)",
        "request_descriptor": descriptor,
        "request_params": request_params,
        "response": response,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)

    with args.json_out.open("w", encoding="utf-8") as f:
        json.dump(json_sanitize(payload), f, ensure_ascii=False, indent=2)

    args.md_out.write_text(
        render_markdown(descriptor=descriptor, cmd=cmd, payload=response),
        encoding="utf-8",
    )
    print(f"\n[Đã ghi JSON -> {args.json_out.resolve()}]")
    print(f"[Đã ghi MD   -> {args.md_out.resolve()}]")


def cmd_history(args: argparse.Namespace) -> None:
    req = {"symbol": args.symbol, "period": args.period, "interval": args.interval}
    t = yf.Ticker(args.symbol)
    hist = t.history(period=args.period, interval=args.interval)
    records = dataframe_to_records(hist)

    descriptor = (
        f'yfinance.Ticker({args.symbol!r}).history(period={args.period!r}, interval={args.interval!r})'
    )
    response: dict[str, Any] = {"symbol": args.symbol, "bars": records, "rows": len(records)}

    print("=== Descriptor ===\n")
    print(descriptor)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(response))
    _write_outputs(args=args, cmd="history", descriptor=descriptor, request_params=req, response=response)


def cmd_info(args: argparse.Namespace) -> None:
    req = {"symbol": args.symbol}
    t = yf.Ticker(args.symbol)
    info_raw = getattr(t, "info", {}) or {}

    descriptor = f"yfinance.Ticker({args.symbol!r}).info"
    response: dict[str, Any] = {"symbol": args.symbol, "info": json_sanitize(dict(info_raw))}

    print("=== Descriptor ===\n")
    print(descriptor)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(response))
    _write_outputs(args=args, cmd="info", descriptor=descriptor, request_params=req, response=response)


def cmd_fast_info(args: argparse.Namespace) -> None:
    req = {"symbol": args.symbol}
    t = yf.Ticker(args.symbol)
    fi = getattr(t, "fast_info", {}) or {}
    raw = dict(fi) if hasattr(fi, "keys") else {}

    descriptor = f"yfinance.Ticker({args.symbol!r}).fast_info"
    response = {"symbol": args.symbol, "fast_info": json_sanitize(raw)}

    print("=== Descriptor ===\n")
    print(descriptor)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(response))
    _write_outputs(args=args, cmd="fast-info", descriptor=descriptor, request_params=req, response=response)


def cmd_news(args: argparse.Namespace) -> None:
    req = {"symbol": args.symbol, "limit": args.limit}
    t = yf.Ticker(args.symbol)
    raw_news = getattr(t, "news", None) or []
    clipped = raw_news[: args.limit] if isinstance(raw_news, list) else raw_news

    descriptor = f"yfinance.Ticker({args.symbol!r}).news"
    response = {"symbol": args.symbol, "articles": json_sanitize(clipped), "count": len(clipped) if isinstance(clipped, list) else 0}

    print("=== Descriptor ===\n")
    print(descriptor)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(response))
    _write_outputs(args=args, cmd="news", descriptor=descriptor, request_params=req, response=response)


def cmd_ticker_batch(args: argparse.Namespace) -> None:
    symbols = list(args.symbols) if args.symbols else ["BTC-USD", "ETH-USD", "SOL-USD"]
    req = {
        "symbols": symbols,
        "period": args.period,
        "interval": args.interval,
    }
    infos: dict[str, Any] = {}
    histories: dict[str, list[dict[str, Any]]] = {}

    for sym in symbols:
        t = yf.Ticker(sym)
        infos[sym] = json_sanitize(dict(getattr(t, "info", {}) or {}))
        h = t.history(period=args.period, interval=args.interval)
        histories[sym] = dataframe_to_records(h)

    descriptor = (
        "Per symbol:\n"
        + "\n".join(
            f'  yfinance.Ticker({s!r}).history(period={args.period!r}, interval={args.interval!r}); .info'
            for s in symbols
        )
    )
    meta = {
        s: {"info_fields": len(infos.get(s, {})), "history_rows": len(histories.get(s, []))}
        for s in symbols
    }
    response = {
        "symbols": symbols,
        "infos": infos,
        "histories": histories,
        "meta": meta,
    }

    print("=== Descriptor ===\n")
    print(descriptor)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(json_sanitize(response)))
    _write_outputs(
        args=args,
        cmd="ticker-batch",
        descriptor=descriptor,
        request_params=req,
        response=response,
    )


def main() -> None:
    ap = argparse.ArgumentParser(description="Yahoo Finance (yfinance) playground")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("fast-info", parents=[_io_parent], help=".fast_info nhẹ (~giá) — mặc định crypto")
    pa.add_argument("--symbol", default="BTC-USD", help="Yahoo ticker, vd. BTC-USD, ETH-USD")
    pa.set_defaults(func=cmd_fast_info)

    pb = sub.add_parser("history", parents=[_io_parent], help=".history OHLCV crypto")
    pb.add_argument("--symbol", default="BTC-USD")
    pb.add_argument("--period", default="1mo")
    pb.add_argument("--interval", default="1d")
    pb.set_defaults(func=cmd_history)

    pc = sub.add_parser("info", parents=[_io_parent], help=".info (cỡ lớn) — ticker crypto Yahoo")
    pc.add_argument("--symbol", default="BTC-USD")
    pc.set_defaults(func=cmd_info)

    pd = sub.add_parser("news", parents=[_io_parent], help=".news gắn mã Yahoo")
    pd.add_argument("--symbol", default="BTC-USD")
    pd.add_argument("--limit", type=int, default=20)
    pd.set_defaults(func=cmd_news)

    pe = sub.add_parser(
        "ticker",
        parents=[_io_parent],
        help="Nhiều mã crypto: .info + .history — không đổi mặc định BTC-USD ETH-USD SOL-USD",
    )
    pe.add_argument("--symbols", nargs="*", metavar="SYM", help="Để trống = BTC-USD ETH-USD SOL-USD")
    pe.add_argument("--period", default="5d")
    pe.add_argument("--interval", default="1d")
    pe.set_defaults(func=cmd_ticker_batch)

    args = ap.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
