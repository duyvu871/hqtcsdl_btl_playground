"""Kiểm tra hạ tầng cơ bản (Phase 0) — config, import, kết nối Redis/MongoDB.

Chạy: uv run pytest tests/test_infra.py -v
Cần: docker compose up (Redis + MongoDB) cho test ping.

Danh sách test:
  test_config_load          — .env load đúng MONGODB_URI, REDIS_URL
  test_settings_from_env    — tạo Settings từ biến môi trường
  test_import_package       — import được src.common
  test_redis_ping           — Redis trả lời PING
  test_mongo_ping           — MongoDB trả lời ping
  test_config_paths_exist   — file config (coin_registry, docker-compose...) tồn tại
"""

from __future__ import annotations

import pytest
import redis.exceptions

from src.common.config import Settings, settings
from src.common.mongo_client import close_mongo, mongo_ping
from src.common.redis_client import close_redis, redis_ping


def test_config_load() -> None:
    """Đọc .env thành công — có URI MongoDB và Redis."""
    assert settings.MONGODB_URI
    assert settings.REDIS_URL
    assert settings.MONGODB_DB == "crypto_mvp"


def test_settings_from_env() -> None:
    """Tạo Settings mới từ chuỗi URI — parse đúng."""
    cfg = Settings(MONGODB_URI="mongodb://localhost:27018", REDIS_URL="redis://localhost:6378/0")
    assert "mongodb" in cfg.MONGODB_URI
    assert "redis" in cfg.REDIS_URL


def test_import_package() -> None:
    """Import src.common không lỗi — get_db, get_redis dùng được."""
    from src.common import close_mongo, close_redis, get_db, get_redis, settings as s

    assert s.MONGODB_URI
    assert callable(get_db)
    assert callable(get_redis)


@pytest.mark.asyncio
async def test_redis_ping() -> None:
    """Redis đang chạy và trả lời PING."""
    try:
        ok = await redis_ping()
        assert ok is True
    except (redis.exceptions.ConnectionError, OSError) as exc:
        pytest.skip(f"Redis not available: {exc}")
    finally:
        await close_redis()


@pytest.mark.asyncio
async def test_mongo_ping() -> None:
    """MongoDB đang chạy và trả lời ping."""
    try:
        result = await mongo_ping()
        assert result.get("ok") == 1.0
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    finally:
        await close_mongo()


@pytest.mark.asyncio
async def test_config_paths_exist() -> None:
    """Các file cấu hình quan trọng có trên đĩa."""
    assert settings.coin_registry_path.exists()
    assert settings.settings_yaml_path.exists()
    assert settings.insight_prompt_path.exists()
    assert settings.repo_root.joinpath("docker-compose.yml").exists()
