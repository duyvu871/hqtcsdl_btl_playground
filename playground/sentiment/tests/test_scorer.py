"""Test đơn giản cho rule_based và schema — không cần MongoDB hay model."""

from __future__ import annotations

import sys
from pathlib import Path

# Thêm parent vào path để import lib
_SENTIMENT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_SENTIMENT_DIR))

from lib.rule_based import rule_based_score  # noqa: E402
from lib.schema import build_sentiment_event, normalize_timestamp  # noqa: E402


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Rule-based tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_rule_based_positive():
    result = rule_based_score("BTC to the moon bullish breakout")
    assert result["sentiment_score"] > 0, f"Expected positive score, got {result['sentiment_score']}"
    assert result["sentiment_label"] == "positive", f"Expected 'positive', got {result['sentiment_label']}"
    assert result["sentiment_model"] == "rule_based_crypto"
    print(f"  [PASS] positive: score={result['sentiment_score']}, label={result['sentiment_label']}")


def test_rule_based_negative():
    result = rule_based_score("ETH crash dump rekt")
    assert result["sentiment_score"] < 0, f"Expected negative score, got {result['sentiment_score']}"
    assert result["sentiment_label"] == "negative", f"Expected 'negative', got {result['sentiment_label']}"
    assert result["sentiment_model"] == "rule_based_crypto"
    print(f"  [PASS] negative: score={result['sentiment_score']}, label={result['sentiment_label']}")


def test_rule_based_neutral():
    result = rule_based_score("Bitcoin price is 65000 today")
    assert result["sentiment_label"] == "neutral", f"Expected 'neutral', got {result['sentiment_label']}"
    assert result["sentiment_model"] == "rule_based_crypto"
    print(f"  [PASS] neutral: score={result['sentiment_score']}, label={result['sentiment_label']}")


def test_rule_based_empty():
    result = rule_based_score("")
    assert result["sentiment_score"] == 0.0
    assert result["sentiment_label"] == "neutral"
    print(f"  [PASS] empty: score={result['sentiment_score']}")


def test_rule_based_mixed():
    result = rule_based_score("BTC bullish rally but also crash fears and fud")
    assert result["sentiment_model"] == "rule_based_crypto"
    print(f"  [PASS] mixed: score={result['sentiment_score']}, label={result['sentiment_label']}")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Schema tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_normalize_timestamp_int():
    assert normalize_timestamp(1716110997) == 1716110997
    print("  [PASS] normalize_timestamp int")


def test_normalize_timestamp_float():
    assert normalize_timestamp(1716110997.5) == 1716110997
    print("  [PASS] normalize_timestamp float")


def test_normalize_timestamp_none():
    assert normalize_timestamp(None) is None
    print("  [PASS] normalize_timestamp None")


def test_normalize_timestamp_iso():
    ts = normalize_timestamp("2026-06-11T00:00:00+00:00")
    assert isinstance(ts, int)
    assert ts > 0
    print(f"  [PASS] normalize_timestamp ISO -> {ts}")


def test_build_sentiment_event_has_required_fields():
    event = {
        "event_id": "e1",
        "mapped_id": "m1",
        "parent_event_id": "p1",
        "coin_id": "BTC",
        "source": "twitter",
        "clean_text": "BTC bullish",
        "author_id": "user_123",
        "metrics": {"followers": 1000, "likes": 50},
        "timestamp": 1716110997,
    }
    result = {
        "sentiment_score": 0.8,
        "sentiment_label": "positive",
        "sentiment_confidence": 0.9,
        "probabilities": {"positive": 0.9, "neutral": 0.05, "negative": 0.05},
        "sentiment_model": "test_model",
    }
    doc = build_sentiment_event(event, result)

    assert doc["coin_id"] == "BTC"
    assert doc["sentiment_score"] == 0.8
    assert doc["sentiment_label"] == "positive"
    assert doc["event_id"] == "e1"
    assert doc["mapped_id"] == "m1"
    assert doc["parent_event_id"] == "p1"
    assert doc["source"] == "twitter"
    assert doc["author_id"] == "user_123"
    assert "sentiment_id" in doc
    assert "scored_at" in doc
    assert doc["timestamp"] == 1716110997
    print("  [PASS] build_sentiment_event — tất cả field đều đúng")


def test_build_sentiment_event_missing_optional_fields():
    event = {
        "event_id": "e2",
        "coin_id": "ETH",
        "clean_text": "ETH dump",
        "timestamp": 1716110997,
    }
    result = {
        "sentiment_score": -0.7,
        "sentiment_label": "negative",
        "sentiment_model": "test_model",
    }
    doc = build_sentiment_event(event, result)

    assert doc["coin_id"] == "ETH"
    assert doc["sentiment_score"] == -0.7
    assert doc["mapped_id"] is None
    assert doc["source"] is None
    assert doc["metrics"] == {}
    print("  [PASS] build_sentiment_event — optional fields → None/default")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Alpha Vantage sentiment tests
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def test_alpha_vantage_sentiment():
    from lib.scorer import try_alpha_vantage_sentiment

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
    assert result["sentiment_score"] == 0.63
    assert result["sentiment_label"] == "positive"
    assert result["sentiment_model"] == "alpha_vantage_news_sentiment"
    print(f"  [PASS] AV sentiment: score={result['sentiment_score']}, label={result['sentiment_label']}")


def test_alpha_vantage_no_ticker():
    from lib.scorer import try_alpha_vantage_sentiment

    event = {"coin_id": "BTC", "extra": {}}
    result = try_alpha_vantage_sentiment(event)
    assert result is None
    print("  [PASS] AV sentiment — no ticker_sentiment → None")


def test_alpha_vantage_wrong_coin():
    from lib.scorer import try_alpha_vantage_sentiment

    event = {
        "coin_id": "SOL",
        "extra": {
            "ticker_sentiment": [
                {
                    "ticker": "CRYPTO:BTC",
                    "relevance_score": "0.9",
                    "ticker_sentiment_score": "0.5",
                    "ticker_sentiment_label": "Bullish",
                }
            ]
        },
    }
    result = try_alpha_vantage_sentiment(event)
    assert result is None
    print("  [PASS] AV sentiment — wrong coin → None")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# Runner
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━


def run_all():
    tests = [
        ("Rule-based: positive", test_rule_based_positive),
        ("Rule-based: negative", test_rule_based_negative),
        ("Rule-based: neutral", test_rule_based_neutral),
        ("Rule-based: empty", test_rule_based_empty),
        ("Rule-based: mixed", test_rule_based_mixed),
        ("Timestamp: int", test_normalize_timestamp_int),
        ("Timestamp: float", test_normalize_timestamp_float),
        ("Timestamp: None", test_normalize_timestamp_none),
        ("Timestamp: ISO", test_normalize_timestamp_iso),
        ("Schema: full fields", test_build_sentiment_event_has_required_fields),
        ("Schema: optional fields", test_build_sentiment_event_missing_optional_fields),
        ("AV: with ticker", test_alpha_vantage_sentiment),
        ("AV: no ticker", test_alpha_vantage_no_ticker),
        ("AV: wrong coin", test_alpha_vantage_wrong_coin),
    ]

    passed = 0
    failed = 0

    print("=" * 60)
    print("  Sentiment Module — Unit Tests")
    print("=" * 60)

    for name, fn in tests:
        try:
            fn()
            passed += 1
        except Exception as exc:
            print(f"  [FAIL] {name}: {exc}")
            failed += 1

    print("=" * 60)
    print(f"  Results: {passed} passed, {failed} failed, {passed + failed} total")
    print("=" * 60)

    return failed == 0


if __name__ == "__main__":
    success = run_all()
    sys.exit(0 if success else 1)
