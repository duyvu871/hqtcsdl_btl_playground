"""Stage 4 business logic — sentiment scoring per mapped_event."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.common.config import settings
from src.pipeline.sentiment.documents import build_sentiment_event
from src.pipeline.sentiment.rule_based import rule_based_score
from src.pipeline.sentiment.scorer import SentimentScorer, try_alpha_vantage_sentiment


@dataclass
class SentimentPipeline:
    """Score mapped_events — AV bypass → FinBERT → rule_based fallback."""

    use_finbert: bool = False
    _scorer: SentimentScorer | None = field(default=None, init=False)

    def __post_init__(self) -> None:
        if self.use_finbert:
            self._scorer = SentimentScorer(model_name=settings.SENTIMENT_MODEL)

    def score(self, mapped_event: dict[str, Any]) -> dict[str, Any]:
        if mapped_event.get("source") == "news":
            av = try_alpha_vantage_sentiment(mapped_event)
            if av is not None:
                return av

        text = str(mapped_event.get("clean_text") or mapped_event.get("raw_text") or "")
        if self._scorer is not None:
            return self._scorer.score_text(text)
        return rule_based_score(text)

    def process(self, mapped_event: dict[str, Any]) -> dict[str, Any]:
        result = self.score(mapped_event)
        return build_sentiment_event(mapped_event, result)


_pipeline: SentimentPipeline | None = None


def get_sentiment_pipeline() -> SentimentPipeline:
    global _pipeline
    if _pipeline is None:
        _pipeline = SentimentPipeline()
    return _pipeline


def reset_sentiment_pipeline() -> None:
    global _pipeline
    _pipeline = None
