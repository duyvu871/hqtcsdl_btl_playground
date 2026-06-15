"""Kiểm tra Sentiment stage (Phase 4) — unit test, không cần MongoDB/Redis.

Chạy rule-based (mặc định):
  uv run pytest tests/test_sentiment.py -v

Chạy thêm FinBERT (cần --extra pipeline, chậm ~10s lần đầu):
  uv run pytest tests/test_sentiment.py -v --finbert

Danh sách test:
  test_tc04_bullish / test_tc05_bearish     — rule_based
  test_tc04_bullish_finbert / ..._finbert   — FinBERT (flag --finbert)
  test_t4_04_metadata_l01                   — L-01 filter_meta + ner_meta
  test_av_bypass                            — Alpha Vantage bypass
  test_rule_based_neutral                   — neutral keywords
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.pipeline.sentiment.documents import build_sentiment_event
from src.pipeline.sentiment.rule_based import rule_based_score
from src.pipeline.sentiment.scorer import SentimentScorer, try_alpha_vantage_sentiment
from src.pipeline.sentiment.service import SentimentPipeline


def _mapped_event(**extra) -> dict:
    base = {
        "mapped_id": "map-001",
        "parent_event_id": "clean-001",
        "event_id": "clean-001",
        "coin_id": "BTC",
        "source": "twitter",
        "clean_text": "BTC to the moon bullish breakout",
        "author_id": "user-1",
        "timestamp": 1_718_380_800,
        "filter": {"stage": "passed", "layers": ["heuristic"]},
        "ner": {"method": "cashtag", "confidence": 0.95},
    }
    base.update(extra)
    return base


def test_tc04_bullish() -> None:
    """Text bullish → score > 0, label positive."""
    result = rule_based_score("BTC to the moon bullish breakout")
    assert result["sentiment_score"] > 0
    assert result["sentiment_label"] == "positive"


def test_tc05_bearish() -> None:
    """Text bearish → score < 0, label negative."""
    result = rule_based_score("ETH crash dump rekt")
    assert result["sentiment_score"] < 0
    assert result["sentiment_label"] == "negative"


@pytest.fixture(scope="module")
def finbert_scorer() -> SentimentScorer:
    """Load FinBERT 1 lần cho cả module — chỉ khi --finbert."""
    pytest.importorskip("transformers")
    return SentimentScorer(use_rule_fallback=False)


@pytest.mark.finbert
def test_tc04_bullish_finbert(finbert_scorer: SentimentScorer) -> None:
    """FinBERT: text bullish → label positive."""
    result = finbert_scorer.score_text("The stock market rallied strongly after positive earnings")
    assert result["method"] == "finbert"
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_score"] > 0


@pytest.mark.finbert
def test_tc05_bearish_finbert(finbert_scorer: SentimentScorer) -> None:
    """FinBERT: text bearish → label negative."""
    result = finbert_scorer.score_text("Shares plunged after the company reported heavy losses")
    assert result["method"] == "finbert"
    assert result["sentiment_label"] == "negative"
    assert result["sentiment_score"] < 0


@pytest.mark.finbert
def test_sentiment_pipeline_finbert() -> None:
    """SentimentPipeline(use_finbert=True) → method finbert."""
    pytest.importorskip("transformers")
    pipeline = SentimentPipeline(use_finbert=True)
    doc = pipeline.process(_mapped_event(clean_text="Markets surged on strong economic data"))
    assert doc["method"] == "finbert"
    assert doc["sentiment_label"] in ("positive", "neutral", "negative")
    assert doc["sentiment_model"] == "ProsusAI/finbert"


def test_t4_04_metadata_l01() -> None:
    """sentiment_events propagate filter_meta và ner_meta từ mapped_event."""
    mapped = _mapped_event()
    pipeline = SentimentPipeline()
    doc = pipeline.process(mapped)

    assert doc["filter_meta"] == mapped["filter"]
    assert doc["ner_meta"] == mapped["ner"]
    assert doc["filter_meta"] != {}
    assert doc["ner_meta"] != {}
    assert doc["coin_id"] == "BTC"
    assert "sentiment_id" in doc


def test_av_bypass() -> None:
    """News có AV ticker_sentiment → dùng av_bypass, không cần FinBERT."""
    event = {
        "coin_id": "BTC",
        "source": "news",
        "extra": {
            "ticker_sentiment": [
                {
                    "ticker": "CRYPTO:BTC",
                    "relevance_score": "0.92",
                    "ticker_sentiment_score": "0.63",
                    "ticker_sentiment_label": "Bullish",
                }
            ]
        },
    }
    result = try_alpha_vantage_sentiment(event)
    assert result is not None
    assert result["method"] == "av_bypass"
    assert result["sentiment_score"] == 0.63
    assert result["sentiment_label"] == "positive"


def test_rule_based_neutral() -> None:
    """Text không có từ khoá sentiment → neutral."""
    result = rule_based_score("Bitcoin price is 65000 today")
    assert result["sentiment_label"] == "neutral"


def test_build_sentiment_event_fields() -> None:
    """build_sentiment_event có đủ field bắt buộc."""
    mapped = _mapped_event(clean_text="ETH dump")
    result = rule_based_score("ETH dump")
    doc = build_sentiment_event(mapped, result)
    assert doc["mapped_id"] == "map-001"
    assert doc["sentiment_score"] == result["sentiment_score"]
    assert doc["sentiment_label"] == result["sentiment_label"]


if __name__ == "__main__":
    run_finbert = "--finbert" in sys.argv
    raise SystemExit(pytest.main([__file__, "-v", *(["--finbert"] if run_finbert else [])]))
