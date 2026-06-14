"""Pytest fixtures and env defaults for infra smoke tests."""

from __future__ import annotations

import os

# Must run before any src.common import (Settings requires MONGODB_URI + REDIS_URL).
# Ports khớp docker-compose.yml (host 6378→redis:6379, host 27018→mongo:27017).
os.environ.setdefault("MONGODB_URI", "mongodb://localhost:27018")
os.environ.setdefault("REDIS_URL", "redis://localhost:6378/0")
os.environ.setdefault("MONGODB_DB", "crypto_mvp")
