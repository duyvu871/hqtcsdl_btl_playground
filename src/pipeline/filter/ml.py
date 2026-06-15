"""L3 — FastText spam classifier (optional nếu có model).

Model: models/spam/spam_model.bin (FASTTEXT_MODEL_PATH)
Không có model → L3 bị skip, cascade chỉ L1+L2.
Cần: uv sync --extra pipeline
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from src.common.config import settings

logger = logging.getLogger(__name__)


def _load_fasttext():
    """Import fasttext — optional dep (dev group hoặc --extra pipeline)."""
    try:
        import fasttext
    except ImportError as e:
        raise RuntimeError(
            "Thiếu fasttext — cài: uv sync hoặc uv sync --extra pipeline"
        ) from e
    return fasttext


@dataclass(frozen=True)
class MlConfig:
    model_path: Path
    spam_threshold: float = 0.5  # P(spam) ≥ ngưỡng → DROP (TC-02)
    skip_news: bool = True


@dataclass(frozen=True)
class MlResult:
    passed: bool
    label: str = "human"
    score: float = 0.0
    skipped: bool = False


class SpamClassifier:
    """Wrapper FastText — fallback skip L3 nếu model không tồn tại."""

    def __init__(self, config: MlConfig) -> None:
        self.config = config
        self._model: Any = None
        if config.model_path.is_file():
            fasttext = _load_fasttext()
            self._model = fasttext.load_model(str(config.model_path))
            logger.info("L3 FastText loaded: %s", config.model_path)
        else:
            logger.warning(
                "L3 FastText skipped — model không tồn tại: %s "
                "(train: playground/finetune/fasttext → models/spam/spam_model.bin)",
                config.model_path,
            )

    @property
    def available(self) -> bool:
        return self._model is not None

    def predict(self, event: dict[str, Any], *, text: str) -> MlResult:
        """Trả passed=False nếu label=spam và score ≥ spam_threshold."""
        source = str(event.get("source") or "")
        if self.config.skip_news and source == "news":
            return MlResult(True, skipped=True)

        if self._model is None:
            return MlResult(True, skipped=True)

        clean = text.replace("\n", " ").strip()
        if not clean:
            return MlResult(True, label="human", score=0.0)

        labels, probs = self._model.predict(clean, k=1)
        if not labels:
            return MlResult(True, label="human", score=0.0)

        label = labels[0].replace("__label__", "")
        score = float(probs[0])
        if label == "spam" and score >= self.config.spam_threshold:
            return MlResult(False, label=label, score=score)
        return MlResult(True, label=label, score=score)


def default_ml_classifier() -> SpamClassifier:
    """Factory — đọc đường dẫn model từ settings.fasttext_model_path_resolved."""
    return SpamClassifier(MlConfig(model_path=settings.fasttext_model_path_resolved))
