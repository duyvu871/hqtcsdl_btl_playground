"""Sentiment scorer dùng HuggingFace transformers pipeline."""

from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

# Label aliases cho các model khác nhau
_POSITIVE_ALIASES = {"pos", "positive", "bullish", "label_2"}
_NEGATIVE_ALIASES = {"neg", "negative", "bearish", "label_0"}
_NEUTRAL_ALIASES = {"neu", "neutral", "label_1"}

# Mapping cho Alpha Vantage ticker
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
    """Chuẩn hoá label từ nhiều model về positive/neutral/negative."""
    label = label.lower().strip()

    if label in _POSITIVE_ALIASES:
        return "positive"
    if label in _NEGATIVE_ALIASES:
        return "negative"
    if label in _NEUTRAL_ALIASES:
        return "neutral"
    return "neutral"


def _normalize_av_label(label: str) -> str:
    """Chuẩn hoá label Alpha Vantage."""
    return _AV_LABEL_MAP.get(label.lower().strip(), "neutral")


def _score_to_label(score: float, threshold: float = 0.15) -> str:
    """Gán label dựa trên score với threshold."""
    if score >= threshold:
        return "positive"
    elif score <= -threshold:
        return "negative"
    return "neutral"


def try_alpha_vantage_sentiment(event: dict[str, Any]) -> dict[str, Any] | None:
    """Nếu event có Alpha Vantage ticker_sentiment, trả về score có sẵn.
    
    Chỉ áp dụng cho source alpha_vantage/news.
    """
    extra = event.get("extra") or {}
    ticker_sentiments = extra.get("ticker_sentiment")
    if not ticker_sentiments:
        return None

    coin_id = event.get("coin_id", "").upper()
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

                # Clamp score
                score = max(-1.0, min(1.0, score))

                return {
                    "sentiment_score": score,
                    "sentiment_label": label,
                    "sentiment_confidence": relevance,
                    "relevance_score": relevance,
                    "probabilities": {},
                    "sentiment_model": "alpha_vantage_news_sentiment",
                }
            except (TypeError, ValueError) as exc:
                logger.warning("Lỗi parse Alpha Vantage sentiment: %s", exc)
                return None

    return None


class SentimentScorer:
    """Chạy sentiment analysis bằng HuggingFace pipeline.
    
    Hỗ trợ các model:
    - ProsusAI/finbert (mặc định, tài chính tiếng Anh)
    - ElKulako/cryptobert (crypto-specific)
    - wonrax/phobert-base-vietnamese-sentiment (tiếng Việt)
    """

    def __init__(
        self,
        model_name: str = "ProsusAI/finbert",
        max_length: int = 256,
        use_rule_fallback: bool = True,
    ) -> None:
        self.model_name = model_name
        self.max_length = max_length
        self.use_rule_fallback = use_rule_fallback
        self._pipeline = None
        self._id2label: dict[int, str] = {}

    def _load_pipeline(self) -> None:
        """Lazy load model — chỉ load khi gọi lần đầu."""
        if self._pipeline is not None:
            return

        logger.info("Loading sentiment model: %s", self.model_name)
        try:
            from transformers import AutoModelForSequenceClassification, pipeline

            # Load model để lấy id2label
            model = AutoModelForSequenceClassification.from_pretrained(self.model_name)
            self._id2label = model.config.id2label or {}

            self._pipeline = pipeline(
                "sentiment-analysis",
                model=model,
                tokenizer=self.model_name,
                truncation=True,
                max_length=self.max_length,
                top_k=None,  # Lấy tất cả probabilities
            )
            logger.info("Model loaded. id2label=%s", self._id2label)
        except Exception as exc:
            logger.error("Không thể load model %s: %s", self.model_name, exc)
            self._pipeline = None
            raise

    def score_text(self, text: str) -> dict[str, Any]:
        """Score một đoạn text. Trả về dict sentiment result.
        
        Nếu model lỗi và use_rule_fallback=True, fallback sang rule-based.
        """
        if not text or not text.strip():
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "sentiment_confidence": 0.0,
                "probabilities": {},
                "sentiment_model": self.model_name,
            }

        try:
            self._load_pipeline()
            assert self._pipeline is not None

            results = self._pipeline(text)

            # top_k=None trả về list of list
            if results and isinstance(results[0], list):
                results = results[0]

            # Build probabilities dict
            probabilities: dict[str, float] = {}
            for item in results:
                raw_label = str(item["label"])
                norm = normalize_label(raw_label)
                probabilities[norm] = round(float(item["score"]), 4)

            # Tính score: positive_prob - negative_prob
            pos_prob = probabilities.get("positive", 0.0)
            neg_prob = probabilities.get("negative", 0.0)
            sentiment_score = pos_prob - neg_prob

            # Clamp
            sentiment_score = max(-1.0, min(1.0, sentiment_score))

            # Label dựa trên score
            sentiment_label = _score_to_label(sentiment_score)

            # Confidence = prob cao nhất
            sentiment_confidence = max(probabilities.values()) if probabilities else 0.0

            return {
                "sentiment_score": round(sentiment_score, 4),
                "sentiment_label": sentiment_label,
                "sentiment_confidence": round(sentiment_confidence, 4),
                "probabilities": probabilities,
                "sentiment_model": self.model_name,
            }

        except Exception as exc:
            logger.warning("Model error cho text '%s...': %s", text[:50], exc)
            if self.use_rule_fallback:
                from lib.rule_based import rule_based_score
                return rule_based_score(text)
            return {
                "sentiment_score": 0.0,
                "sentiment_label": "neutral",
                "sentiment_confidence": 0.0,
                "probabilities": {},
                "sentiment_model": f"{self.model_name}_error",
            }
