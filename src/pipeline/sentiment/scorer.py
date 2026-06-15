"""Sentiment scorer — FinBERT + Alpha Vantage bypass + rule fallback."""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING, Any

from src.pipeline.sentiment.rule_based import rule_based_score

if TYPE_CHECKING:
    from transformers.pipelines.text_classification import TextClassificationPipeline

logger = logging.getLogger(__name__)

_POSITIVE_ALIASES = {"pos", "positive", "bullish", "label_2"}
_NEGATIVE_ALIASES = {"neg", "negative", "bearish", "label_0"}
_NEUTRAL_ALIASES = {"neu", "neutral", "label_1"}

COIN_TO_AV_TICKER: dict[str, str] = {
    "BTC": "CRYPTO:BTC",
    "ETH": "CRYPTO:ETH",
    "SOL": "CRYPTO:SOL",
    "BNB": "CRYPTO:BNB",
    "XRP": "CRYPTO:XRP",
    "ADA": "CRYPTO:ADA",
    "DOGE": "CRYPTO:DOGE",
    "DOT": "CRYPTO:DOT",
    "AVAX": "CRYPTO:AVAX",
    "MATIC": "CRYPTO:MATIC",
}

_AV_LABEL_MAP: dict[str, str] = {
    "bullish": "positive",
    "somewhat-bullish": "positive",
    "bearish": "negative",
    "somewhat-bearish": "negative",
    "neutral": "neutral",
}


def normalize_label(label: str) -> str:
    label = label.lower().strip()
    if label in _POSITIVE_ALIASES:
        return "positive"
    if label in _NEGATIVE_ALIASES:
        return "negative"
    if label in _NEUTRAL_ALIASES:
        return "neutral"
    return "neutral"


def _normalize_av_label(label: str) -> str:
    return _AV_LABEL_MAP.get(label.lower().strip(), "neutral")


def _score_to_label(score: float, threshold: float = 0.15) -> str:
    if score >= threshold:
        return "positive"
    if score <= -threshold:
        return "negative"
    return "neutral"


def try_alpha_vantage_sentiment(event: dict[str, Any]) -> dict[str, Any] | None:
    """AV bypass — dùng ticker_sentiment có sẵn từ news ingest."""
    extra = event.get("extra") or {}
    ticker_sentiments = extra.get("ticker_sentiment")
    if not ticker_sentiments:
        overall_score = extra.get("overall_sentiment_score")
        overall_label = extra.get("overall_sentiment_label")
        if event.get("source") == "news" and overall_score is not None:
            try:
                score = float(overall_score)
                score = max(-1.0, min(1.0, score))
                return {
                    "sentiment_score": score,
                    "sentiment_label": _normalize_av_label(str(overall_label or "neutral")),
                    "sentiment_confidence": 0.8,
                    "probabilities": {},
                    "method": "av_bypass",
                    "sentiment_model": "alpha_vantage_news_sentiment",
                }
            except (TypeError, ValueError):
                return None
        return None

    coin_id = str(event.get("coin_id", "")).upper()
    target_ticker = COIN_TO_AV_TICKER.get(coin_id)
    if not target_ticker:
        return None

    for item in ticker_sentiments:
        ticker = str(item.get("ticker", "")).upper()
        if ticker == target_ticker:
            try:
                score = float(item.get("ticker_sentiment_score", 0))
                relevance = float(item.get("relevance_score", 1.0))
                raw_label = str(item.get("ticker_sentiment_label", "neutral"))
                label = _normalize_av_label(raw_label)
                score = max(-1.0, min(1.0, score))
                return {
                    "sentiment_score": score,
                    "sentiment_label": label,
                    "sentiment_confidence": relevance,
                    "probabilities": {},
                    "method": "av_bypass",
                    "sentiment_model": "alpha_vantage_news_sentiment",
                }
            except (TypeError, ValueError) as exc:
                logger.warning("Lỗi parse Alpha Vantage sentiment: %s", exc)
                return None

    return None


class SentimentScorer:
    """FinBERT lazy-load; fallback rule_based khi model unavailable."""

    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        max_length: int = 256,
        use_rule_fallback: bool = True,
    ) -> None:
        self.model_name = model_name
        self.max_length = max_length
        self.use_rule_fallback = use_rule_fallback
        self._pipeline: TextClassificationPipeline | None = None

    def _load_pipeline(self) -> None:
        if self._pipeline is not None:
            return

        logger.info("Loading sentiment model: %s", self.model_name)
        from transformers import AutoModelForSequenceClassification, AutoTokenizer
        from transformers.pipelines.text_classification import TextClassificationPipeline

        tokenizer = AutoTokenizer.from_pretrained(self.model_name)
        model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
        self._pipeline = TextClassificationPipeline(
            model=model,
            tokenizer=tokenizer,
            truncation=True,
            max_length=self.max_length,
            top_k=None,
        )

    def score_text(self, text: str) -> dict[str, Any]:
        if not text or not text.strip():
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "sentiment_confidence": 0.0,
                "probabilities": {},
                "method": "finbert",
                "sentiment_model": self.model_name,
            }

        try:
            self._load_pipeline()
            assert self._pipeline is not None

            results = self._pipeline(text)
            if results and isinstance(results[0], list):
                results = results[0]

            probabilities: dict[str, float] = {}
            for item in results:
                if not isinstance(item, dict):
                    continue
                label_val = item.get("label")
                score_val = item.get("score")
                if label_val is None or score_val is None:
                    continue
                raw_label = str(label_val)
                norm = normalize_label(raw_label)
                probabilities[norm] = round(float(score_val), 4)

            pos_prob = probabilities.get("positive", 0.0)
            neg_prob = probabilities.get("negative", 0.0)
            sentiment_score = max(-1.0, min(1.0, pos_prob - neg_prob))
            sentiment_label = _score_to_label(sentiment_score)
            sentiment_confidence = max(probabilities.values()) if probabilities else 0.0

            return {
                "sentiment_score": round(sentiment_score, 4),
                "sentiment_label": sentiment_label,
                "sentiment_confidence": round(sentiment_confidence, 4),
                "probabilities": probabilities,
                "method": "finbert",
                "sentiment_model": self.model_name,
            }
        except Exception as exc:
            logger.warning("FinBERT error: %s", exc)
            if self.use_rule_fallback:
                return rule_based_score(text)
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "sentiment_confidence": 0.0,
                "probabilities": {},
                "method": "finbert",
                "sentiment_model": f"{self.model_name}_error",
            }

    def score_event(self, mapped_event: dict[str, Any]) -> dict[str, Any]:
        """Score mapped_event — AV bypass cho news trước, rồi FinBERT/rule."""
        if mapped_event.get("source") == "news":
            av = try_alpha_vantage_sentiment(mapped_event)
            if av is not None:
                return av

        text = str(mapped_event.get("clean_text") or mapped_event.get("raw_text") or "")
        return self.score_text(text)
