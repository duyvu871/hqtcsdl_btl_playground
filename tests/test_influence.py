"""Kiểm tra Influence stage (Phase 5) — unit test, không cần MongoDB/Redis.

Chạy: uv run pytest tests/test_influence.py -v

Danh sách test:
  test_tc06_verified_high_rt          — TC-06 influence weight Twitter verified
  test_raw_engagement_retweet_weight  — retweet > like weight
  test_build_weighted_event_fields    — weighted_event schema fields
  test_aggregate_window_fields        — T5-01 influence_aggregates fields
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.pipeline.influence.aggregate import build_aggregate_doc, window_start_ts, timeframe_seconds
from src.pipeline.influence.documents import build_weighted_event
from src.pipeline.influence.scoring import calculate_influence, raw_engagement


def test_raw_engagement_retweet_weight() -> None:
    """Retweet có trọng số cao hơn like — 1 RT ≈ 4 likes."""
    event_like = {"metrics": {"likes": 4}}
    event_rt = {"metrics": {"retweets": 1}}
    assert raw_engagement(event_rt) == raw_engagement(event_like)


def test_tc06_verified_high_rt() -> None:
    """TC-06: Twitter verified 3M followers, 749 likes, 113 RT → 0 < weight ≤ 20."""
    event = {
        "coin_id": "BTC",
        "source": "twitter",
        "timestamp": 1_893_456_000,
        "sentiment_score": 0.8,
        "sentiment_confidence": 0.9,
        "metrics": {
            "followers": 3_000_000,
            "likes": 749,
            "retweets": 113,
            "verified": True,
        },
    }
    detail = calculate_influence(event, reference_ts=1_893_456_000)
    assert 0 < detail["influence_weight"] <= 20
    for field in (
        "author_authority",
        "engagement_strength",
        "virality_surprise",
        "source_weight",
        "time_decay",
        "quality_score",
    ):
        assert field in detail


def test_build_weighted_event_fields() -> None:
    """weighted_event có influence_weight + weighted_sentiment."""
    event = {
        "sentiment_id": "sent_1",
        "event_id": "evt_1",
        "coin_id": "BTC",
        "source": "twitter",
        "timestamp": 1_893_456_000,
        "sentiment_score": 0.5,
        "sentiment_label": "positive",
        "sentiment_confidence": 1.0,
        "metrics": {"followers": 1000, "likes": 100},
    }
    doc = build_weighted_event(event, reference_ts=1_893_456_000)
    assert doc["source_event_key"] == "sent_1"
    assert doc["coin_id"] == "BTC"
    assert "influence_weight" in doc
    assert "weighted_sentiment" in doc
    assert doc["influence"]["influence_weight"] == doc["influence_weight"]


def test_aggregate_window_fields() -> None:
    """T5-01: influence_aggregates có đủ field schema."""
    ts = 1_718_380_800
    ws = window_start_ts(ts, timeframe_seconds("1h"))
    bucket = [
        {
            "sentiment_score": 0.5,
            "influence_weight": 2.0,
            "weighted_sentiment": 1.0,
            "sentiment_label": "positive",
        },
        {
            "sentiment_score": -0.3,
            "influence_weight": 1.0,
            "weighted_sentiment": -0.3,
            "sentiment_label": "negative",
        },
    ]
    agg = build_aggregate_doc("BTC", ws, bucket, timeframe="1h")
    assert agg["coin_id"] == "BTC"
    assert agg["timeframe"] == "1h"
    assert agg["window_start"] is not None
    assert "sentiment_score" in agg
    assert agg["social_volume"] == 2
    assert agg["event_count"] == 2
