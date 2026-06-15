"""CLI Orchestrator — tạo session và monitor control stream.

Usage:
  uv run python -m src.orchestrator run --coin BTC --timeframe 1h
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from src.orchestrator.monitor import monitor_session
from src.orchestrator.session import create_session

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def _run(coin: str, timeframe: str, sources: list[str] | None) -> None:
    result = await create_session(
        coin,
        timeframe,
        sources=sources,
        user_message=f"Phân tích {coin.upper()} khung {timeframe}",
    )
    session_id = result["session_id"]
    job_id = result["job_id"]
    logger.info("Session created: %s job=%s", session_id, job_id)
    logger.info("Kickoff published → stage:ingest:in")
    logger.info("Monitoring control stream (Ctrl+C to stop)...")

    status = await monitor_session(session_id, job_id)
    logger.info("Monitor finished: status=%s", status)


def main() -> None:
    parser = argparse.ArgumentParser(description="Crypto Social Intelligence Orchestrator")
    sub = parser.add_subparsers(dest="command", required=True)

    run_parser = sub.add_parser("run", help="Tạo session + monitor pipeline")
    run_parser.add_argument("--coin", default="BTC")
    run_parser.add_argument("--timeframe", default="1h")
    run_parser.add_argument(
        "--sources",
        nargs="*",
        default=None,
        help="Ingest sources: twitter news-av news-yahoo reddit",
    )

    args = parser.parse_args()
    if args.command == "run":
        asyncio.run(_run(args.coin, args.timeframe, args.sources))


if __name__ == "__main__":
    main()
