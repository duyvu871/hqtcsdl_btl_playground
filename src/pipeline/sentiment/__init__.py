"""Stage 4 — Sentiment analysis per coin-event."""

from src.pipeline.sentiment.documents import build_sentiment_event, normalize_timestamp
from src.pipeline.sentiment.rule_based import rule_based_score
from src.pipeline.sentiment.scorer import SentimentScorer, try_alpha_vantage_sentiment
from src.pipeline.sentiment.service import SentimentPipeline, get_sentiment_pipeline, reset_sentiment_pipeline
from src.pipeline.sentiment.worker import sentiment_processor

__all__ = [
    "SentimentPipeline",
    "SentimentScorer",
    "build_sentiment_event",
    "get_sentiment_pipeline",
    "normalize_timestamp",
    "reset_sentiment_pipeline",
    "rule_based_score",
    "sentiment_processor",
    "try_alpha_vantage_sentiment",
]
