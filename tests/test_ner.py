"""Kiểm tra NER stage (Phase 4) — unit test, không cần MongoDB/Redis/API.

Chạy: uv run pytest tests/test_ner.py -v

Danh sách test:
  test_tc03_cashtag_btc          — $BTC → coin_id BTC, method cashtag
  test_t4_03_keyword_bitcoin     — "bitcoin" → coin_id BTC, method keyword
  test_t4_01_fanout_two_coins    — BTC + ETH → 2 mapped_events cùng parent
  test_t4_01_no_mention          — text không liên quan → 0 mapped
"""

from __future__ import annotations

import sys
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

from src.pipeline.ner.pipeline import NerMode, map_event
from src.pipeline.ner.registry import CoinRegistry
from src.pipeline.ner.service import NerPipeline, reset_ner_pipeline


def _clean_event(text: str, **extra) -> dict:
    return {
        "event_id": "clean-001",
        "source": "twitter",
        "clean_text": text,
        "raw_text": text,
        "author_id": "user-1",
        "metrics": {"likes": 10},
        "timestamp": 1_718_380_800,
        "filter": {"stage": "passed", "layers": ["heuristic"]},
        **extra,
    }


def test_tc03_cashtag_btc() -> None:
    """$BTC trong text → map coin_id=BTC, ner.method=cashtag."""
    registry = CoinRegistry.load()
    outcome = map_event(
        _clean_event("Buy $BTC now before breakout"),
        mode=NerMode.HYBRID,
        registry=registry,
        llm=None,
    )
    assert len(outcome.mentions) == 1
    assert outcome.mentions[0].coin_id == "BTC"
    assert outcome.mentions[0].method == "cashtag"


def test_t4_03_keyword_bitcoin() -> None:
    """"bitcoin" → coin_id=BTC, method=keyword."""
    registry = CoinRegistry.load()
    outcome = map_event(
        _clean_event("bitcoin looking strong today"),
        mode=NerMode.HYBRID,
        registry=registry,
        llm=None,
    )
    assert len(outcome.mentions) == 1
    assert outcome.mentions[0].coin_id == "BTC"
    assert outcome.mentions[0].method == "keyword"


def test_t4_01_fanout_two_coins() -> None:
    """Tweet đề cập BTC và ETH → 2 mapped_events, cùng parent_event_id."""
    reset_ner_pipeline()
    pipeline = NerPipeline()
    _, docs = pipeline.process(_clean_event("Rotation from $BTC into $ETH looks likely"))

    assert len(docs) == 2
    coin_ids = {d["coin_id"] for d in docs}
    assert coin_ids == {"BTC", "ETH"}
    assert all(d["parent_event_id"] == "clean-001" for d in docs)
    assert all(d["mapped_id"] != d["coin_id"] for d in docs)
    assert all("ner" in d and d["ner"]["method"] in ("cashtag", "keyword") for d in docs)


def test_t4_01_no_mention() -> None:
    """Text không map được coin → không fan-out."""
    reset_ner_pipeline()
    pipeline = NerPipeline()
    _, docs = pipeline.process(_clean_event("Federal Reserve holds rates steady in March meeting"))
    assert docs == []


if __name__ == "__main__":
    import pytest

    raise SystemExit(pytest.main([__file__, "-v"]))
