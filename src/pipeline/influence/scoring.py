"""Công thức tính influence cho từng sentiment_event (Stage 5)."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from typing import Any

from src.common.config import settings

SOURCE_WEIGHTS: dict[str, float] = {
    "twitter": 1.00,
    "x": 1.00,
    "reddit": 0.90,
    "news": 1.15,
    "alpha_vantage": 1.15,
    "yahoo_finance": 1.10,
}

PUBLISHER_WEIGHTS: dict[str, float] = {
    "reuters": 1.80,
    "bloomberg": 1.80,
    "cnbc": 1.55,
    "coindesk": 1.45,
    "cointelegraph": 1.30,
    "yahoo": 1.10,
}


def to_float(value: Any, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def clamp(value: float, lower: float = 0.0, upper: float = 1.0) -> float:
    return max(lower, min(upper, value))


def sigmoid(x: float) -> float:
    if x >= 60:
        return 1.0
    if x <= -60:
        return 0.0
    return 1.0 / (1.0 + math.exp(-x))


def normalize_timestamp(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return int(value)
    if isinstance(value, datetime):
        return int(value.timestamp())
    if isinstance(value, str):
        try:
            return int(float(value))
        except (TypeError, ValueError):
            pass
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return int(dt.timestamp())
        except (TypeError, ValueError):
            return None
    return None


def now_ts() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def half_life_hours_for_source(source: str | None) -> float:
    source_key = (source or "").strip().lower()
    if source_key in {"twitter", "x"}:
        return settings.TWITTER_HALF_LIFE_HOURS
    if source_key == "reddit":
        return settings.REDDIT_HALF_LIFE_HOURS
    if source_key in {"news", "alpha_vantage", "yahoo_finance"}:
        return settings.NEWS_HALF_LIFE_HOURS
    return settings.DEFAULT_HALF_LIFE_HOURS


def get_verified(event: dict[str, Any]) -> bool:
    metrics = event.get("metrics") or {}
    candidates = (
        event.get("is_verified"),
        event.get("verified"),
        metrics.get("is_verified"),
        metrics.get("verified"),
    )
    return any(value is True or str(value).lower() == "true" for value in candidates)


def raw_engagement(event: dict[str, Any]) -> float:
    metrics = event.get("metrics") or {}

    likes = to_float(metrics.get("likes"))
    replies = to_float(metrics.get("replies"))
    comments = to_float(metrics.get("comments"))
    quotes = to_float(metrics.get("quotes"))
    retweets = to_float(metrics.get("retweets"))
    shares = to_float(metrics.get("shares"))
    bookmarks = to_float(metrics.get("bookmarks"))
    impressions = to_float(metrics.get("impressions"))
    views = to_float(metrics.get("views"))
    reddit_score = to_float(metrics.get("score"))

    return max(
        0.0,
        1.0 * likes
        + 2.0 * replies
        + 2.0 * comments
        + 3.0 * quotes
        + 4.0 * retweets
        + 4.0 * shares
        + 1.5 * bookmarks
        + 0.001 * impressions
        + 0.001 * views
        + 1.0 * reddit_score,
    )


def source_weight(event: dict[str, Any]) -> float:
    source = str(event.get("source") or "").strip().lower()
    base = SOURCE_WEIGHTS.get(source, 1.0)

    if source in {"news", "alpha_vantage", "yahoo_finance"}:
        publisher_text = " ".join(
            str(event.get(key) or "").lower()
            for key in ("news_provider", "source_name", "publisher", "author_id")
        )
        for keyword, weight in PUBLISHER_WEIGHTS.items():
            if keyword in publisher_text:
                return max(base, weight)

    return base


def time_decay(event: dict[str, Any], *, reference_ts: int | None = None) -> float:
    timestamp = normalize_timestamp(event.get("timestamp"))
    if timestamp is None:
        return 0.5

    ref = reference_ts if reference_ts is not None else now_ts()
    age_hours = max(0.0, (ref - timestamp) / 3600.0)
    half_life = max(0.1, half_life_hours_for_source(event.get("source")))

    return math.exp(-math.log(2.0) * age_hours / half_life)


def quality_score(event: dict[str, Any]) -> float:
    ner = event.get("ner") or event.get("ner_meta") or {}
    filter_meta = event.get("filter") or event.get("filter_meta") or {}

    sentiment_confidence = to_float(event.get("sentiment_confidence"), 1.0)
    ner_confidence = to_float(ner.get("confidence"), 1.0)

    spam_probability = to_float(
        filter_meta.get("spam_probability", filter_meta.get("spam_score")),
        0.0,
    )
    duplicate_penalty = to_float(filter_meta.get("duplicate_penalty"), 1.0)

    score = (
        clamp(sentiment_confidence)
        * clamp(ner_confidence)
        * (1.0 - clamp(spam_probability))
        * clamp(duplicate_penalty)
    )
    return clamp(score)


def author_authority(event: dict[str, Any]) -> float:
    metrics = event.get("metrics") or {}

    followers = to_float(metrics.get("followers"))
    avg_author_engagement = to_float(
        metrics.get("avg_author_engagement", event.get("avg_author_engagement"))
    )
    account_age_days = to_float(
        metrics.get("account_age_days", event.get("account_age_days"))
    )
    verified = 1.0 if get_verified(event) else 0.0

    follower_score = sigmoid(math.log1p(max(0.0, followers)) / 10.0)
    avg_engagement_score = sigmoid(math.log1p(max(0.0, avg_author_engagement)) / 8.0)
    age_score = sigmoid(math.log1p(max(0.0, account_age_days)) / 8.0)

    has_avg = avg_author_engagement > 0
    has_age = account_age_days > 0

    if has_avg and has_age:
        score = 0.45 * follower_score + 0.30 * avg_engagement_score + 0.15 * age_score + 0.10 * verified
    elif has_avg:
        score = 0.55 * follower_score + 0.35 * avg_engagement_score + 0.10 * verified
    else:
        score = 0.85 * follower_score + 0.15 * verified

    return clamp(score)


def engagement_strength(event: dict[str, Any]) -> float:
    engagement_log = math.log1p(raw_engagement(event))
    return sigmoid(engagement_log / 8.0)


def virality_surprise(event: dict[str, Any]) -> float:
    metrics = event.get("metrics") or {}
    current = raw_engagement(event)
    expected = to_float(
        metrics.get(
            "expected_author_engagement",
            metrics.get("avg_author_engagement", event.get("avg_author_engagement")),
        ),
        settings.DEFAULT_EXPECTED_ENGAGEMENT,
    )
    expected = max(1.0, expected)
    surprise = math.log1p(current / expected)
    return sigmoid(surprise)


def network_influence(event: dict[str, Any]) -> float:
    metrics = event.get("metrics") or {}
    return clamp(to_float(metrics.get("pagerank_score", event.get("pagerank_score")), 0.0))


def calculate_influence(event: dict[str, Any], *, reference_ts: int | None = None) -> dict[str, float]:
    """Tính chi tiết influence cho một sentiment_event."""
    s_src = source_weight(event)
    t_decay = time_decay(event, reference_ts=reference_ts)
    q_score = quality_score(event)

    a_score = author_authority(event)
    e_score = engagement_strength(event)
    v_score = virality_surprise(event)
    p_score = network_influence(event)
    raw_eng = raw_engagement(event)

    core = (
        settings.ALPHA_AUTHOR * a_score
        + settings.BETA_ENGAGEMENT * e_score
        + settings.GAMMA_VIRALITY * v_score
        + settings.DELTA_NETWORK * p_score
    )

    influence = s_src * t_decay * q_score * (1.0 + settings.CORE_SCALE * core)
    influence = min(settings.MAX_INFLUENCE, max(0.0, influence))

    return {
        "source_weight": round(s_src, 6),
        "time_decay": round(t_decay, 6),
        "quality_score": round(q_score, 6),
        "author_authority": round(a_score, 6),
        "engagement_strength": round(e_score, 6),
        "virality_surprise": round(v_score, 6),
        "network_influence": round(p_score, 6),
        "raw_engagement": round(raw_eng, 6),
        "core_score": round(core, 6),
        "influence_weight": round(influence, 6),
    }
