"""Fallback rule-based sentiment scorer cho crypto slang."""

from __future__ import annotations

import re
from typing import Any

# ── Positive crypto words / phrases ──────────────────────────────────────────
POSITIVE_WORDS: set[str] = {
    "moon", "to the moon", "bullish", "pump", "breakout", "buy",
    "long", "ath", "wagmi", "gem", "accumulate", "rally", "green",
    "surge", "soar", "rocket", "diamond hands", "hodl", "hold",
    "lambo", "mooning", "parabolic", "gm", "lfg", "alpha",
    "undervalued", "dip buy", "buy the dip", "btd", "up only",
}

# ── Negative crypto words / phrases ──────────────────────────────────────────
NEGATIVE_WORDS: set[str] = {
    "rekt", "dump", "bearish", "crash", "scam", "rug", "rugpull",
    "rug pull", "short", "fud", "hack", "hacked", "liquidated",
    "blood", "red", "sell", "ponzi", "dead", "ngmi", "exit scam",
    "plunge", "plummet", "capitulation", "collapse", "tank",
    "tanking", "bubble", "fraud", "exploit", "drain", "drained",
}

# Pre-compile multi-word patterns
_POSITIVE_MULTI = {w for w in POSITIVE_WORDS if " " in w}
_POSITIVE_SINGLE = {w for w in POSITIVE_WORDS if " " not in w}
_NEGATIVE_MULTI = {w for w in NEGATIVE_WORDS if " " in w}
_NEGATIVE_SINGLE = {w for w in NEGATIVE_WORDS if " " not in w}


def _tokenize(text: str) -> list[str]:
    """Tokenize text thành list từ đơn (lowercase, bỏ ký tự đặc biệt)."""
    return re.findall(r"[a-z0-9]+", text.lower())


def rule_based_score(text: str) -> dict[str, Any]:
    """Tính sentiment score dựa trên từ khoá crypto.
    
    Returns:
        dict với sentiment_score, sentiment_label, sentiment_confidence,
        sentiment_model.
    """
    if not text or not text.strip():
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "neutral",
            "sentiment_confidence": 0.0,
            "probabilities": {},
            "sentiment_model": "rule_based_crypto",
        }

    text_lower = text.lower()
    tokens = _tokenize(text)
    token_set = set(tokens)

    pos_count = 0
    neg_count = 0

    # Check multi-word phrases
    for phrase in _POSITIVE_MULTI:
        if phrase in text_lower:
            pos_count += 1
    for phrase in _NEGATIVE_MULTI:
        if phrase in text_lower:
            neg_count += 1

    # Check single words
    pos_count += len(token_set & _POSITIVE_SINGLE)
    neg_count += len(token_set & _NEGATIVE_SINGLE)

    total = pos_count + neg_count

    if total == 0:
        return {
            "sentiment_score": 0.0,
            "sentiment_label": "neutral",
            "sentiment_confidence": 0.0,
            "probabilities": {"positive": 0.0, "neutral": 1.0, "negative": 0.0},
            "sentiment_model": "rule_based_crypto",
        }

    # Score: tỷ lệ positive vs negative, scale [-1, 1]
    raw_score = (pos_count - neg_count) / total
    # Confidence dựa trên số lượng matches
    confidence = min(1.0, total / 5.0)  # cap tại 5 matches = 100% confidence
    # Weighted score
    sentiment_score = round(raw_score * confidence, 4)
    sentiment_score = max(-1.0, min(1.0, sentiment_score))

    # Label
    if sentiment_score >= 0.15:
        label = "positive"
    elif sentiment_score <= -0.15:
        label = "negative"
    else:
        label = "neutral"

    # Approximate probabilities
    pos_prob = round(pos_count / max(total, 1), 4)
    neg_prob = round(neg_count / max(total, 1), 4)
    neu_prob = round(max(0.0, 1.0 - pos_prob - neg_prob), 4)

    return {
        "sentiment_score": sentiment_score,
        "sentiment_label": label,
        "sentiment_confidence": round(confidence, 4),
        "probabilities": {
            "positive": pos_prob,
            "neutral": neu_prob,
            "negative": neg_prob,
        },
        "sentiment_model": "rule_based_crypto",
    }
