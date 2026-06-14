"""Pytest fixtures and env defaults for infra smoke tests."""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Repo root on sys.path (belt-and-suspenders alongside pyproject pythonpath).
_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

# Must run before any src.common import (Settings requires MONGODB_URI + REDIS_URL).
# Ports khớp docker-compose.yml (host 6378→redis:6379, host 27018→mongo:27017).
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27018")
os.environ.setdefault("REDIS_URL", "redis://localhost:6378/0")
os.environ.setdefault("MONGODB_DB", "crypto_mvp")
