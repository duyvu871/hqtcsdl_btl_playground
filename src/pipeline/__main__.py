"""Pipeline worker entrypoint — chạy liên tục, nhận payload từ Redis Streams và xử lý.

Khởi động 7 asyncio tasks song song, mỗi task là 1 stage worker với vòng lặp vô hạn:

    XREADGROUP (block 5s) → processor() → persist MongoDB → XADD next stream → XACK

Luồng dữ liệu:
    stage:ingest:in → filter → ner → sentiment → influence → scoring → insight → (terminal)

Usage:
    uv run --extra pipeline python -m src.pipeline                     # tất cả 7 workers
    uv run --extra pipeline python -m src.pipeline --stages ingest filter  # chỉ 1 số stage
    uv run --extra pipeline python -m src.pipeline --once              # 1 batch rồi dừng (test)

Cần khởi động SAU khi API server đã chạy (API tạo session + XADD kickoff vào stage:ingest:in).
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import signal
import sys

from src.pipeline._runtime.worker import process_batch, run

from src.pipeline.ingest.worker import ingest_processor
from src.pipeline.filter.worker import filter_processor
from src.pipeline.ner.worker import ner_processor
from src.pipeline.sentiment.worker import sentiment_processor
from src.pipeline.influence.worker import influence_processor
from src.pipeline.scoring.worker import scoring_processor
from src.pipeline.insight.worker import insight_processor

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("pipeline.main")

# Stage name → processor function
STAGES: dict[str, object] = {
    "ingest":    ingest_processor,
    "filter":    filter_processor,
    "ner":       ner_processor,
    "sentiment": sentiment_processor,
    "influence": influence_processor,
    "scoring":   scoring_processor,
    "insight":   insight_processor,
}


async def _run_once(stages: list[str]) -> None:
    """Xử lý 1 batch/stage rồi dừng — dùng để test."""
    from src.common.redis_client import get_redis
    redis = await get_redis()
    for stage in stages:
        processor = STAGES[stage]
        n = await process_batch(
            redis,
            stage,
            processor,  # type: ignore[arg-type]
            block_ms=2000,
        )
        logger.info("Stage %-12s: processed %d entries", stage, n)


async def _run_all(stages: list[str]) -> None:
    """Khởi động tất cả workers song song (vòng lặp vô hạn)."""
    logger.info("Starting %d workers: %s", len(stages), ", ".join(stages))

    tasks = []
    for stage in stages:
        processor = STAGES[stage]
        task = asyncio.create_task(
            run(stage, processor),  # type: ignore[arg-type]
            name=f"worker:{stage}",
        )
        tasks.append(task)
        logger.info("  ✓ worker:%s started", stage)

    # Graceful shutdown on SIGINT/SIGTERM
    loop = asyncio.get_running_loop()
    stop_event = asyncio.Event()

    def _shutdown(sig: int) -> None:
        logger.info("Received signal %s, shutting down...", signal.Signals(sig).name)
        stop_event.set()
        for t in tasks:
            t.cancel()

    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, _shutdown, sig)

    logger.info("All workers running. Press Ctrl+C to stop.")
    try:
        results = await asyncio.gather(*tasks, return_exceptions=True)
        # Log bất kỳ task nào kết thúc bất thường
        for task, result in zip(tasks, results):
            if isinstance(result, BaseException) and not isinstance(result, asyncio.CancelledError):
                logger.error("Task %s exited with error: %s", task.get_name(), result, exc_info=result)
    except asyncio.CancelledError:
        pass
    logger.info("Workers stopped.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Crypto Social Intelligence — Pipeline Workers"
    )
    parser.add_argument(
        "--stages",
        nargs="*",
        default=list(STAGES.keys()),
        choices=list(STAGES.keys()),
        metavar="STAGE",
        help="Stages to run (default: all). Options: " + ", ".join(STAGES.keys()),
    )
    parser.add_argument(
        "--once",
        action="store_true",
        help="Xử lý 1 batch/stage rồi dừng (dùng để test)",
    )
    args = parser.parse_args()

    stages = args.stages or list(STAGES.keys())
    unknown = [s for s in stages if s not in STAGES]
    if unknown:
        logger.error("Unknown stages: %s", unknown)
        sys.exit(1)

    if args.once:
        asyncio.run(_run_once(stages))
    else:
        asyncio.run(_run_all(stages))


if __name__ == "__main__":
    main()
