from lib.schema import build_weighted_event
from lib.scoring import calculate_influence, raw_engagement


def test_raw_engagement_weights_retweet_more_than_like():
    event_like = {"metrics": {"likes": 4}}
    event_rt = {"metrics": {"retweets": 1}}
    assert raw_engagement(event_rt) == raw_engagement(event_like)


def test_calculate_influence_has_required_fields():
    event = {
        "coin_id": "BTC",
        "source": "twitter",
        "timestamp": 1893456000,
        "sentiment_score": 0.8,
        "sentiment_confidence": 0.9,
        "metrics": {
            "followers": 100000,
            "likes": 1000,
            "retweets": 200,
            "replies": 50,
            "verified": True,
        },
    }
    detail = calculate_influence(event, reference_ts=1893456000)
    assert 0 < detail["influence_weight"] <= 20
    assert "author_authority" in detail
    assert "engagement_strength" in detail
    assert "virality_surprise" in detail


def test_build_weighted_event_matches_stage6_fields():
    event = {
        "sentiment_id": "sent_1",
        "event_id": "evt_1",
        "coin_id": "BTC",
        "source": "twitter",
        "timestamp": 1893456000,
        "sentiment_score": 0.5,
        "sentiment_label": "positive",
        "sentiment_confidence": 1.0,
        "metrics": {"followers": 1000, "likes": 100},
    }
    doc = build_weighted_event(event, reference_ts=1893456000)
    assert doc["source_event_key"] == "sent_1"
    assert doc["coin_id"] == "BTC"
    assert "influence_weight" in doc
    assert "weighted_sentiment" in doc
