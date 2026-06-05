"""L3 — FastText spam classifier (optional nếu có model)."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import fasttext


@dataclass(frozen=True)
class MlConfig:
    model_path: Path
    spam_threshold: float = 0.5
    skip_news: bool = True


@dataclass(frozen=True)
class MlResult:
    passed: bool
    label: str = "human"
    score: float = 0.0
    skipped: bool = False


class SpamClassifier:
    def __init__(self, config: MlConfig) -> None:
        self.config = config
        self._model: fasttext.FastText._FastText | None = None
        if config.model_path.is_file():
            self._model = fasttext.load_model(str(config.model_path))

    @property
    def available(self) -> bool:
        return self._model is not None

    def predict(self, event: dict[str, Any], *, text: str) -> MlResult:
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
