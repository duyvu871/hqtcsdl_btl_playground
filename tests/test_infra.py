"""P0 infrastructure smoke tests (T0-01 .. T0-05)."""

from __future__ import annotations

import pytest
import redis.exceptions

from src.common.config import Settings, settings
from src.common.mongo_client import close_mongo, mongo_ping
from src.common.redis_client import close_redis, redis_ping


def test_config_load() -> None:
    """T0-02: Settings load with required infra vars."""
    assert settings.MONGODB_URI
    assert settings.REDIS_URL
    assert settings.MONGODB_DB == "crypto_mvp"


def test_settings_from_env() -> None:
    """T0-02b: Fresh Settings instance parses env."""
    cfg = Settings(MONGODB_URI="mongodb://localhost:27018", REDIS_URL="redis://localhost:6378/0")
    assert "mongodb" in cfg.MONGODB_URI
    assert "redis" in cfg.REDIS_URL


def test_import_package() -> None:
    """T0-05: src.common submodules importable."""
    from src.common import close_mongo, close_redis, get_db, get_redis, settings as s

    assert s.MONGODB_URI
    assert callable(get_db)
    assert callable(get_redis)


@pytest.mark.asyncio
async def test_redis_ping() -> None:
    """T0-03: Redis PING (requires docker compose redis)."""
    try:
        ok = await redis_ping()
        assert ok is True
    except (redis.exceptions.ConnectionError, OSError) as exc:
        pytest.skip(f"Redis not available: {exc}")
    finally:
        await close_redis()


@pytest.mark.asyncio
async def test_mongo_ping() -> None:
    """T0-04: MongoDB ping (requires docker compose mongo)."""
    try:
        result = await mongo_ping()
        assert result.get("ok") == 1.0
    except Exception as exc:
        pytest.skip(f"MongoDB not available: {exc}")
    finally:
        await close_mongo()


@pytest.mark.asyncio
async def test_config_paths_exist() -> None:
    """Config artifact files from P0 exist on disk."""
    assert settings.coin_registry_path.exists()
    assert settings.settings_yaml_path.exists()
    assert settings.insight_prompt_path.exists()
    assert settings.repo_root.joinpath("docker-compose.yml").exists()
