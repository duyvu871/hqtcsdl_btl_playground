#!/usr/bin/env python3
"""
Alpha Vantage — playground **crypto** (digital currency + tỉ giá + tin).

Không gọi endpoint cổ phiếu cổ điển (OVERVIEW, TIME_SERIES_DAILY_ADJUSTED cổ phiếu, RSI equity).

Examples:
  export ALPHA_VANTAGE_API_KEY="..."
  python run.py exchange-rate --from-ccy BTC --to-ccy USD
  python run.py crypto-daily --symbol BTC --market USD
  python run.py crypto-intraday --symbol ETH --market USD --interval 5min
  python run.py news --tickers CRYPTO:BTC --json-out btc_news.json --md-out btc_news.md
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from av_client import (
    BASE_URL,
    fetch,
    parse_body_as_json_or_raw,
    pretty_snippet,
    render_markdown,
    to_av_time,
)

_SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_JSON_OUT = _SCRIPT_DIR / "alphavantage_response.json"
DEFAULT_MD_OUT = _SCRIPT_DIR / "alphavantage_response.md"

_io_parent = argparse.ArgumentParser(add_help=False)
_io_parent.add_argument(
    "--json-out",
    type=Path,
    default=DEFAULT_JSON_OUT,
    metavar="PATH",
    help=f"Ghi JSON (default: {DEFAULT_JSON_OUT.name})",
)
_io_parent.add_argument(
    "--md-out",
    type=Path,
    default=DEFAULT_MD_OUT,
    metavar="PATH",
    help=f"Ghi Markdown (default: {DEFAULT_MD_OUT.name})",
)
_io_parent.add_argument("--no-save", action="store_true", help="Chỉ in stdout")


def _write_outputs(
    *,
    args: argparse.Namespace,
    cmd: str,
    params: dict,
    url_disp: str,
    body: str,
) -> None:
    if args.no_save:
        return

    payload = {
        "command": cmd,
        "request_url_redacted": url_disp,
        "request_params_redacted": {
            **{k: ("***" if k == "apikey" else v) for k, v in params.items()},
        },
        "response": parse_body_as_json_or_raw(body),
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.md_out.parent.mkdir(parents=True, exist_ok=True)

    with args.json_out.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    args.md_out.write_text(
        render_markdown(url_disp=url_disp, body=body, cmd=cmd),
        encoding="utf-8",
    )
    print(f"\n[Đã ghi JSON -> {args.json_out.resolve()}]")
    print(f"[Đã ghi MD   -> {args.md_out.resolve()}]")


def _run(fn: str, params: dict, args: argparse.Namespace, cmd_name: str) -> None:
    p = {"function": fn, **params}
    url_disp, body = fetch(p)
    print("=== Request (GET) ===\n")
    print(url_disp)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(body))
    _write_outputs(args=args, cmd=cmd_name, params=p, url_disp=url_disp, body=body)


def cmd_exchange_rate(args: argparse.Namespace) -> None:
    """CURRENCY_EXCHANGE_RATE — tỉ giá 1 crypto/fiat sang cặp khác (BTC↔USD, …)."""
    _run(
        "CURRENCY_EXCHANGE_RATE",
        {
            "from_currency": args.from_ccy.upper(),
            "to_currency": args.to_ccy.upper(),
        },
        args,
        "exchange-rate",
    )


def cmd_crypto_daily(args: argparse.Namespace) -> None:
    """DIGITAL_CURRENCY_DAILY — giá/ngày theo market fiat hoặc stablecoin."""
    _run(
        "DIGITAL_CURRENCY_DAILY",
        {
            "symbol": args.symbol.upper(),
            "market": args.market.upper(),
        },
        args,
        "crypto-daily",
    )


def cmd_crypto_weekly(args: argparse.Namespace) -> None:
    _run(
        "DIGITAL_CURRENCY_WEEKLY",
        {
            "symbol": args.symbol.upper(),
            "market": args.market.upper(),
        },
        args,
        "crypto-weekly",
    )


def cmd_crypto_monthly(args: argparse.Namespace) -> None:
    _run(
        "DIGITAL_CURRENCY_MONTHLY",
        {
            "symbol": args.symbol.upper(),
            "market": args.market.upper(),
        },
        args,
        "crypto-monthly",
    )


def cmd_crypto_intraday(args: argparse.Namespace) -> None:
    """CRYPTO_INTRADAY — OHLCV intraday (theo Alpha Vantage #crypto-intraday)."""
    _run(
        "CRYPTO_INTRADAY",
        {
            "symbol": args.symbol.upper(),
            "market": args.market.upper(),
            "interval": args.interval,
            "outputsize": args.outputsize,
        },
        args,
        "crypto-intraday",
    )


def cmd_news(args: argparse.Namespace) -> None:
    """NEWS_SENTIMENT — tickers ví dụ: CRYPTO:BTC, CRYPTOCURRENCY_ETH (theo docs AV)."""
    now = datetime.now(timezone.utc)
    start = now - timedelta(days=args.days)
    p = {
        "function": "NEWS_SENTIMENT",
        "tickers": args.tickers,
        "time_from": to_av_time(start),
        "time_to": to_av_time(now),
        "limit": str(args.limit),
        "sort": "RELEVANCE",
    }
    if getattr(args, "topics", None):
        p["topics"] = args.topics
    url_disp, body = fetch(p)
    print("=== Request (GET) ===\n")
    print(url_disp)
    print("\n=== Response (snippet, stdout) ===\n")
    print(pretty_snippet(body))
    _write_outputs(args=args, cmd="news", params=p, url_disp=url_disp, body=body)


def main() -> None:
    ap = argparse.ArgumentParser(description="Alpha Vantage — crypto / digital currency only → JSON + MD")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pa = sub.add_parser("exchange-rate", parents=[_io_parent], help="CURRENCY_EXCHANGE_RATE (ví dụ BTC→USD)")
    pa.add_argument("--from-ccy", default="BTC", dest="from_ccy")
    pa.add_argument("--to-ccy", default="USD", dest="to_ccy")
    pa.set_defaults(func=cmd_exchange_rate)

    pb = sub.add_parser("crypto-daily", parents=[_io_parent], help="DIGITAL_CURRENCY_DAILY")
    pb.add_argument("--symbol", default="BTC")
    pb.add_argument("--market", default="USD")
    pb.set_defaults(func=cmd_crypto_daily)

    pw = sub.add_parser("crypto-weekly", parents=[_io_parent], help="DIGITAL_CURRENCY_WEEKLY")
    pw.add_argument("--symbol", default="BTC")
    pw.add_argument("--market", default="USD")
    pw.set_defaults(func=cmd_crypto_weekly)

    pm = sub.add_parser("crypto-monthly", parents=[_io_parent], help="DIGITAL_CURRENCY_MONTHLY")
    pm.add_argument("--symbol", default="BTC")
    pm.add_argument("--market", default="USD")
    pm.set_defaults(func=cmd_crypto_monthly)

    pi = sub.add_parser("crypto-intraday", parents=[_io_parent], help="CRYPTO_INTRADAY OHLCV intraday")
    pi.add_argument("--symbol", default="BTC")
    pi.add_argument("--market", default="USD")
    pi.add_argument(
        "--interval",
        default="60min",
        choices=("1min", "5min", "15min", "30min", "60min"),
    )
    pi.add_argument(
        "--outputsize",
        choices=("compact", "full"),
        default="compact",
        help="compact ≈ 100 điểm; full = chuỗi dài hơn (tuỳ quota AV)",
    )
    pi.set_defaults(func=cmd_crypto_intraday)

    pn = sub.add_parser("news", parents=[_io_parent], help="NEWS_SENTIMENT — tickers crypto")
    pn.add_argument("--tickers", default="CRYPTO:BTC")
    pn.add_argument(
        "--topics",
        default=None,
        help="Tuỳ chọn — vd. cryptocurrency, blockchain (theo Alpha Vantage)",
    )
    pn.add_argument("--days", type=int, default=7)
    pn.add_argument("--limit", type=int, default=20)
    pn.set_defaults(func=cmd_news)

    args = ap.parse_args()
    print(f"(Base endpoint: {BASE_URL})\n")
    args.func(args)


if __name__ == "__main__":
    main()