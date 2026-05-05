#!/usr/bin/env python3
"""
Filter Alpha Vantage NEWS_SENTIMENT response into agent-friendly JSON/Markdown.

Input is the envelope produced by ``run.py news``:
  {
    "command": "news",
    "request_params_redacted": {...},
    "response": {"feed": [...]}
  }
"""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT = SCRIPT_DIR / "alphavantage_response.json"


def _float(v: Any, default: float = 0.0) -> float:
    try:
        return float(v)
    except (TypeError, ValueError):
        return default


def _parse_av_time(v: str | None) -> str | None:
    if not v:
        return None
    try:
        return datetime.strptime(v, "%Y%m%dT%H%M%S").isoformat()
    except ValueError:
        try:
            return datetime.strptime(v, "%Y%m%dT%H%M").isoformat()
        except ValueError:
            return v


def _wanted_tickers(raw: str | None) -> set[str]:
    if not raw:
        return set()
    return {x.strip().upper() for x in raw.split(",") if x.strip()}


def _short_topics(article: dict[str, Any]) -> list[dict[str, Any]]:
    topics = []
    for t in article.get("topics") or []:
        topics.append(
            {
                "topic": t.get("topic"),
                "relevance_score": _float(t.get("relevance_score")),
            }
        )
    topics.sort(key=lambda x: x["relevance_score"], reverse=True)
    return topics[:3]


def _relevant_ticker_sentiment(
    article: dict[str, Any],
    wanted: set[str],
    min_relevance: float,
) -> list[dict[str, Any]]:
    rows = []
    for item in article.get("ticker_sentiment") or []:
        ticker = str(item.get("ticker", "")).upper()
        relevance = _float(item.get("relevance_score"))
        if wanted and ticker not in wanted:
            continue
        if relevance < min_relevance:
            continue
        sentiment = _float(item.get("ticker_sentiment_score"))
        rows.append(
            {
                "ticker": ticker,
                "relevance_score": relevance,
                "sentiment_score": sentiment,
                "sentiment_label": item.get("ticker_sentiment_label"),
            }
        )
    rows.sort(key=lambda x: x["relevance_score"], reverse=True)
    return rows


def _weighted_sentiment(rows: list[dict[str, Any]]) -> dict[str, dict[str, Any]]:
    bucket: dict[str, dict[str, float | int]] = {}
    for row in rows:
        for ts in row["ticker_sentiment"]:
            ticker = ts["ticker"]
            b = bucket.setdefault(ticker, {"weighted_sum": 0.0, "weight": 0.0, "articles": 0})
            rel = ts["relevance_score"]
            b["weighted_sum"] = float(b["weighted_sum"]) + ts["sentiment_score"] * rel
            b["weight"] = float(b["weight"]) + rel
            b["articles"] = int(b["articles"]) + 1

    out: dict[str, dict[str, Any]] = {}
    for ticker, b in bucket.items():
        weight = float(b["weight"])
        avg = float(b["weighted_sum"]) / weight if weight else 0.0
        out[ticker] = {
            "articles": int(b["articles"]),
            "weighted_sentiment_score": round(avg, 4),
            "avg_relevance": round(weight / int(b["articles"]), 4) if b["articles"] else 0.0,
        }
    return out


def _label_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        label = row.get("overall_sentiment_label") or "Unknown"
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda x: x[0]))


def build_useful_payload(
    envelope: dict[str, Any],
    *,
    min_relevance: float,
    top: int,
) -> dict[str, Any]:
    params = envelope.get("request_params_redacted") or {}
    wanted = _wanted_tickers(params.get("tickers"))
    response = envelope.get("response") or {}
    feed = response.get("feed") or []

    useful_articles = []
    for i, article in enumerate(feed, start=1):
        ticker_sentiment = _relevant_ticker_sentiment(article, wanted, min_relevance)
        if wanted and not ticker_sentiment:
            continue
        max_rel = max((x["relevance_score"] for x in ticker_sentiment), default=0.0)
        max_abs_sentiment = max((abs(x["sentiment_score"]) for x in ticker_sentiment), default=0.0)
        impact_score = round(max_rel * max_abs_sentiment, 4)
        useful_articles.append(
            {
                "rank_in_source": i,
                "published_at": _parse_av_time(article.get("time_published")),
                "source": article.get("source"),
                "source_domain": article.get("source_domain"),
                "title": article.get("title"),
                "summary": article.get("summary"),
                "url": article.get("url"),
                "overall_sentiment_score": _float(article.get("overall_sentiment_score")),
                "overall_sentiment_label": article.get("overall_sentiment_label"),
                "ticker_sentiment": ticker_sentiment,
                "topics": _short_topics(article),
                "impact_score": impact_score,
            }
        )

    useful_articles.sort(
        key=lambda x: (x["impact_score"], max((t["relevance_score"] for t in x["ticker_sentiment"]), default=0.0)),
        reverse=True,
    )
    if top > 0:
        useful_articles = useful_articles[:top]

    return {
        "source_command": envelope.get("command"),
        "request": {
            "tickers": params.get("tickers"),
            "time_from": params.get("time_from"),
            "time_to": params.get("time_to"),
            "limit": params.get("limit"),
            "sort": params.get("sort"),
        },
        "filters": {
            "min_ticker_relevance": min_relevance,
            "top": top if top > 0 else None,
        },
        "summary": {
            "input_articles": len(feed),
            "kept_articles": len(useful_articles),
            "overall_sentiment_counts": _label_counts(useful_articles),
            "ticker_sentiment": _weighted_sentiment(useful_articles),
        },
        "articles": useful_articles,
    }


def render_markdown(payload: dict[str, Any]) -> str:
    lines: list[str] = [
        "# Alpha Vantage useful news",
        "",
        "## Summary",
        "",
        f"- **Tickers:** `{payload['request'].get('tickers')}`",
        f"- **Window:** `{payload['request'].get('time_from')}` → `{payload['request'].get('time_to')}`",
        f"- **Input articles:** {payload['summary']['input_articles']}",
        f"- **Kept articles:** {payload['summary']['kept_articles']}",
        "",
        "### Ticker Sentiment",
        "",
        "| Ticker | Articles | Weighted Sentiment | Avg Relevance |",
        "| --- | ---: | ---: | ---: |",
    ]
    for ticker, row in payload["summary"]["ticker_sentiment"].items():
        lines.append(
            f"| `{ticker}` | {row['articles']} | {row['weighted_sentiment_score']} | {row['avg_relevance']} |"
        )

    lines.extend(["", "### Overall Label Counts", "", "| Label | Count |", "| --- | ---: |"])
    for label, n in payload["summary"]["overall_sentiment_counts"].items():
        lines.append(f"| {label} | {n} |")

    lines.extend(["", "## Articles", ""])
    for i, article in enumerate(payload["articles"], start=1):
        lines.extend(
            [
                f"### {i}. {article['title']}",
                "",
                f"- **Published:** {article['published_at']}",
                f"- **Source:** {article['source']} (`{article['source_domain']}`)",
                f"- **Overall:** {article['overall_sentiment_label']} ({article['overall_sentiment_score']})",
                f"- **Impact score:** {article['impact_score']}",
                f"- **URL:** {article['url']}",
                "",
                "**Ticker sentiment:**",
                "",
                "| Ticker | Relevance | Sentiment | Label |",
                "| --- | ---: | ---: | --- |",
            ]
        )
        for ts in article["ticker_sentiment"]:
            lines.append(
                f"| `{ts['ticker']}` | {ts['relevance_score']} | {ts['sentiment_score']} | {ts['sentiment_label']} |"
            )
        topics = ", ".join(f"{x['topic']} ({x['relevance_score']})" for x in article["topics"]) or "n/a"
        lines.extend(["", f"**Topics:** {topics}", "", "**Summary:**", "", article["summary"] or "", ""])
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description="Filter Alpha Vantage NEWS_SENTIMENT response.")
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--json-out", type=Path, default=None)
    parser.add_argument("--md-out", type=Path, default=None)
    parser.add_argument("--min-relevance", type=float, default=0.3)
    parser.add_argument("--top", type=int, default=20, help="0 = keep all")
    args = parser.parse_args()

    envelope = json.loads(args.input.read_text(encoding="utf-8"))
    payload = build_useful_payload(envelope, min_relevance=args.min_relevance, top=args.top)

    json_out = args.json_out or args.input.with_name(args.input.stem + "_useful.json")
    md_out = args.md_out or args.input.with_name(args.input.stem + "_useful.md")
    json_out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    md_out.write_text(render_markdown(payload), encoding="utf-8")

    print(f"Wrote JSON -> {json_out}")
    print(f"Wrote MD   -> {md_out}")
    print(f"Kept {payload['summary']['kept_articles']} / {payload['summary']['input_articles']} articles")


if __name__ == "__main__":
    main()
