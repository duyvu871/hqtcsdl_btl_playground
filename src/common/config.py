"""Centralized environment configuration (Pydantic BaseSettings)."""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

_REPO_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """Load from .env at repo root; MONGODB_URI and REDIS_URL are required."""

    # Default khớp .env.example / docker-compose — env var vẫn override khi có
    MONGODB_URI: str = "mongodb://localhost:27018"
    MONGODB_DB: str = "crypto_mvp"
    REDIS_URL: str = "redis://localhost:6378/0"

    RAPIDAPI_KEY: str = ""
    ALPHA_VANTAGE_API_KEY: str = ""
    OPENROUTER_API_KEY: str = ""
    OPENROUTER_INSIGHT_MODEL: str = "anthropic/claude-3.5-sonnet"
    OPENROUTER_MODEL: str = ""

    NER_MODE: str = "hybrid"
    SENTIMENT_MODEL: str = "ProsusAI/finbert"

    # Stage 5 — influence weighting
    MAX_INFLUENCE: float = 20.0
    CORE_SCALE: float = 8.0
    ALPHA_AUTHOR: float = 0.35
    BETA_ENGAGEMENT: float = 0.40
    GAMMA_VIRALITY: float = 0.25
    DELTA_NETWORK: float = 0.0
    DEFAULT_EXPECTED_ENGAGEMENT: float = 50.0
    INFLUENCE_TIMEFRAME: str = "1h"
    TWITTER_HALF_LIFE_HOURS: float = 12.0
    REDDIT_HALF_LIFE_HOURS: float = 24.0
    NEWS_HALF_LIFE_HOURS: float = 36.0
    DEFAULT_HALF_LIFE_HOURS: float = 24.0

    # Stage 6 — scoring
    SCORING_WINDOW: int = 12
    SCORING_MIN_CANDLES: int = 15
    SCORING_OHLCV_LIMIT: int = 48
    SCORING_CARA_LAMBDA: float = 1.2

    REDDIT_CLIENT_ID: str = ""
    REDDIT_CLIENT_SECRET: str = ""
    REDDIT_USERNAME: str = ""
    REDDIT_PASSWORD: str = ""
    REDDIT_USER_AGENT: str = "linux:crypto-social-intelligence:v0.1"

    FASTTEXT_MODEL_PATH: str = "models/spam/spam_model.bin"
    STREAM_MAXLEN: int = 50_000
    STREAM_CLAIM_IDLE_MS: int = 30_000
    STREAM_MAX_RETRY: int = 3
    SESSION_TTL_DAYS: int = 7

    model_config = SettingsConfigDict(
        env_file=str(_REPO_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    @property
    def repo_root(self) -> Path:
        return _REPO_ROOT

    @property
    def config_dir(self) -> Path:
        return _REPO_ROOT / "config"

    @property
    def coin_registry_path(self) -> Path:
        return self.config_dir / "coin_registry.json"

    @property
    def settings_yaml_path(self) -> Path:
        return self.config_dir / "settings.yaml"

    @property
    def insight_prompt_path(self) -> Path:
        return self.config_dir / "prompts" / "insight_v1.txt"

    @property
    def openrouter_model_resolved(self) -> str:
        return self.OPENROUTER_MODEL or self.OPENROUTER_INSIGHT_MODEL

    @property
    def fasttext_model_path_resolved(self) -> Path:
        path = Path(self.FASTTEXT_MODEL_PATH)
        if path.is_absolute():
            return path
        return _REPO_ROOT / path


def get_settings() -> Settings:
    return Settings()


settings = get_settings()
