"""Fixture dùng chung cho toàn bộ tests/.

- Thêm repo root vào sys.path (chạy được python tests/xxx.py trực tiếp)
- Set mặc định MONGODB_URI / REDIS_URL trỏ localhost Docker nếu chưa có .env
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

# Repo root on sys.path (belt-and-suspenders alongside pyproject pythonpath).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Must run before any src.common import (Settings requires MONGODB_URI + REDIS_URL).
# Ports khớp docker-compose.yml (host 6378→redis:6379, host 27018→mongo:27017).
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27018")
os.environ.setdefault("REDIS_URL", "redis://localhost:6378/0")
os.environ.setdefault("MONGODB_DB", "crypto_mvp")


def pytest_addoption(parser) -> None:
    parser.addoption(
        "--finbert",
        action="store_true",
        default=False,
        help="Chạy test sentiment dùng FinBERT (cần uv sync --extra pipeline, chậm)",
    )


def pytest_configure(config) -> None:
    config.addinivalue_line(
        "markers",
        "finbert: sentiment tests với ProsusAI/finbert — cần pytest --finbert",
    )


def pytest_collection_modifyitems(config, items) -> None:
    if config.getoption("--finbert"):
        return
    skip_finbert = pytest.mark.skip(reason="Bỏ qua FinBERT — chạy: pytest --finbert")
    for item in items:
        if "finbert" in item.keywords:
            item.add_marker(skip_finbert)
