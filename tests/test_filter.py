"""P3 Filter unit tests — TC-01, TC-02, T3-04, T3-05 (không cần MongoDB/Redis)."""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

import pytest

from src.pipeline.filter.cascade import run_single
from src.pipeline.filter.dedup import DedupState
from src.pipeline.filter.documents import build_clean_doc, build_dropped_doc
from src.pipeline.filter.heuristic import HeuristicConfig, check_heuristic
from src.pipeline.filter.ml import MlConfig, MlResult, SpamClassifier
from src.pipeline.filter.service import FilterPipeline, reset_filter_pipeline


def _raw_event(text: str, **extra) -> dict:
    """Factory raw event mẫu cho tests."""
    return {
        "event_id": "evt-test-001",
        "source": "twitter",
        "raw_text": text,
        "author_id": "user-1",
        "metrics": {"likes": 100, "retweets": 10, "followers": 50_000},
        "timestamp": 1_718_380_800,
        **extra,
    }


# ── TC-01: L1 pump regex ─────────────────────────────────────────────────────
def test_tc01_pump_regex_drop() -> None:
    """TC-01: Tweet pump → DROP tại L1, drop_reason=pump_regex."""
    event = _raw_event("🚀🚀 100x BUY NOW!!! Guaranteed profit join our telegram t.me/scam")
    result = check_heuristic(event, config=HeuristicConfig(), author_counts={})
    assert result.passed is False
    assert result.reason == "pump_regex"

    outcome = run_single(event, heuristic=HeuristicConfig(), ml=None, dedup=DedupState())
    assert outcome.passed is False
    assert outcome.stage == "L1"
    assert outcome.reason == "pump_regex"

    dropped = build_dropped_doc(event, outcome)
    assert dropped["drop_stage"] == "L1"
    assert dropped["drop_reason"] == "pump_regex"


# ── TC-02: L3 FastText spam ───────────────────────────────────────────────────
class _MockSpamClassifier(SpamClassifier):
    """Mock classifier luôn trả spam — test L3 không cần model file."""

    def __init__(self) -> None:
        self.config = MlConfig(model_path=Path("/dev/null"))

    @property
    def available(self) -> bool:
        return True

    def predict(self, event, *, text: str) -> MlResult:
        return MlResult(False, label="spam", score=0.92)


def test_tc02_fasttext_spam_drop() -> None:
    """TC-02: P(spam) ≥ 0.5 → DROP tại L3."""
    event = _raw_event("Click here for free crypto giveaway now")
    ml = _MockSpamClassifier()
    outcome = run_single(event, heuristic=HeuristicConfig(), ml=ml, dedup=DedupState())

    assert outcome.passed is False
    assert outcome.stage == "L3"
    assert outcome.reason == "fasttext_spam"

    dropped = build_dropped_doc(event, outcome)
    assert dropped["drop_stage"] == "L3"
    assert dropped["drop_reason"] == "fasttext_spam"


# ── T3-04: Tweet hợp lệ PASS ─────────────────────────────────────────────────
def test_t3_04_normal_tweet_passes() -> None:
    """T3-04: Tweet hợp lệ → PASS L1/L2/L3 (cần text không bị FastText gắn spam)."""
    event = _raw_event(
        "Federal Reserve holds rates steady in March meeting"
    )
    reset_filter_pipeline()
    pipeline = FilterPipeline(ml=None)
    clean, dropped = pipeline.process(event)

    assert clean is not None
    assert dropped is None
    assert clean["event_id"] == event["event_id"]
    assert clean["filter"]["stage"] == "passed"
    assert "heuristic" in clean["filter"]["layers"]


# ── T3-05: Recall benchmark (mẫu nhỏ) ─────────────────────────────────────────
# Tập label thủ công — spam phải bị DROP, ham phải PASS
_BENCHMARK = [
    ("🚀 100x gem! Join t.me/pump now!!!", False),
    ("FREE AIRDROP claim your tokens DM me", False),
    ("Bitcoin ETF sees steady inflows this week", True),
    ("ETH gas fees drop after network upgrade", True),
    ("Guaranteed profit presale ends tonight whitelist spot", False),
    ("Market analysis: BTC consolidating near support", True),
    ("To the moon! 1000x potential buy now", False),
    ("Federal Reserve holds rates steady in March meeting", True),
]


def test_t3_05_filter_recall_benchmark() -> None:
    """T3-05: Recall ≥ 85% spam bị DROP trên tập mẫu."""
    reset_filter_pipeline()
    pipeline = FilterPipeline(ml=None)
    dedup = DedupState()

    spam_total = 0
    spam_caught = 0
    ham_total = 0
    ham_passed = 0

    for text, should_pass in _BENCHMARK:
        event = _raw_event(text, event_id=f"bench-{hash(text)}")
        outcome = run_single(event, heuristic=HeuristicConfig(), ml=None, dedup=dedup)
        if should_pass:
            ham_total += 1
            if outcome.passed:
                ham_passed += 1
        else:
            spam_total += 1
            if not outcome.passed:
                spam_caught += 1

    recall = spam_caught / spam_total if spam_total else 1.0
    precision_ham = ham_passed / ham_total if ham_total else 1.0

    assert recall >= 0.85, f"Spam recall {recall:.0%} < 85%"
    assert precision_ham >= 0.75, f"Ham pass rate {precision_ham:.0%} too low"


# ── L3 model missing ─────────────────────────────────────────────────────────
def test_l3_skips_when_model_missing(caplog) -> None:
    """L3 bỏ qua và log warning khi không có spam_model.bin."""
    import logging

    caplog.set_level(logging.WARNING, logger="src.pipeline.filter.ml")
    clf = SpamClassifier(MlConfig(model_path=Path("/nonexistent/spam_model.bin")))

    assert clf.available is False
    assert any("model không tồn tại" in record.message for record in caplog.records)


# ── L2 simhash duplicate ─────────────────────────────────────────────────────
def test_l2_simhash_duplicate() -> None:
    dedup = DedupState()
    event1 = _raw_event("Bitcoin price analysis for today market outlook")
    event2 = _raw_event("Bitcoin price analysis for today market outlook!")

    o1 = run_single(event1, heuristic=HeuristicConfig(), dedup=dedup)
    o2 = run_single(event2, heuristic=HeuristicConfig(), dedup=dedup)

    assert o1.passed is True
    assert o2.passed is False
    assert o2.reason == "simhash_duplicate"


# ── News bypass L1 metrics ───────────────────────────────────────────────────
def test_news_source_skips_engagement_checks() -> None:
    event = {
        "event_id": "news-1",
        "source": "news",
        "raw_text": "Bitcoin reaches new weekly high amid ETF demand",
        "author_id": "Reuters",
        "metrics": {},
        "timestamp": 1_718_380_800,
    }
    result = check_heuristic(event, config=HeuristicConfig(min_likes=9999))
    assert result.passed is True


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
