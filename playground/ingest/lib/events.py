"""Chuẩn hóa nguồn API → document raw event (contract Stage 1 trong pipeline-overview)."""

from __future__ import annotations

import re
import uuid
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from html import unescape
from typing import Any


def _parse_timestamp(created_at: str | None) -> int:
    """Chuyển chuỗi thời gian sang Unix timestamp (giây, UTC)."""
    if not created_at:
        return int(datetime.now(timezone.utc).timestamp())
    try:
        dt = parsedate_to_datetime(created_at)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except (TypeError, ValueError, OverflowError):
        pass

    # Alpha Vantage: YYYYMMDDTHHMMSS hoặc YYYYMMDDTHHMM
    raw = str(created_at).strip()
    for fmt in ("%Y%m%dT%H%M%S", "%Y%m%dT%H%M"):
        try:
            dt = datetime.strptime(raw, fmt).replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            continue

    return int(datetime.now(timezone.utc).timestamp())


def _strip_html(text: str) -> str:
    if not text:
        return ""
    cleaned = unescape(re.sub(r"<[^>]+>", " ", text))
    return re.sub(r"\s+", " ", cleaned).strip()


def _yahoo_article_url(data: dict[str, Any]) -> str:
    for key in ("clickThroughUrl", "canonicalUrl", "previewUrl"):
        val = data.get(key)
        if isinstance(val, dict):
            url = str(val.get("url") or "").strip()
            if url:
                return url
        elif isinstance(val, str) and val.strip():
            return val.strip()
    return str(data.get("link") or data.get("url") or "").strip()


def _parse_yahoo_timestamp(raw: Any) -> int:
    if isinstance(raw, (int, float)) and raw > 0:
        return int(raw)
    if isinstance(raw, str) and raw.strip():
        iso = raw.strip().replace("Z", "+00:00")
        try:
            dt = datetime.fromisoformat(iso)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return int(dt.timestamp())
        except ValueError:
            return _parse_timestamp(raw)
    return int(datetime.now(timezone.utc).timestamp())


def normalize_yahoo_article(article: dict[str, Any]) -> dict[str, Any] | None:
    """
    Chuẩn hóa item từ yfinance Ticker.news.

    yfinance ≥0.2.40 trả schema mới: { id, content: { title, summary, pubDate, ... } }.
    Schema cũ (flat title/link/publisher) vẫn được hỗ trợ.
    Trả None nếu không có title/summary/description usable.
    """
    if not isinstance(article, dict):
        return None

    nested = article.get("content")
    content: dict[str, Any] = nested if isinstance(nested, dict) else article

    title = str(content.get("title") or article.get("title") or "").strip()
    summary = _strip_html(str(content.get("summary") or article.get("summary") or ""))
    description = _strip_html(str(content.get("description") or article.get("description") or ""))
    body = summary or description

    raw_text = title
    if body and body.lower() != title.lower():
        raw_text = f"{title}\n\n{body}" if title else body
    raw_text = raw_text.strip()
    if not raw_text:
        return None

    provider = content.get("provider")
    if isinstance(provider, dict):
        publisher = str(provider.get("displayName") or provider.get("sourceId") or "").strip()
    else:
        publisher = ""
    if not publisher:
        publisher = str(content.get("publisher") or article.get("publisher") or "yahoo_finance").strip()

    link = _yahoo_article_url(content) or _yahoo_article_url(article)
    external_id = str(
        article.get("id")
        or content.get("id")
        or article.get("uuid")
        or content.get("uuid")
        or link
        or title
    ).strip()

    ts_raw = (
        content.get("pubDate")
        or content.get("displayTime")
        or content.get("providerPublishTime")
        or article.get("providerPublishTime")
    )

    extra: dict[str, Any] = {}
    content_type = content.get("contentType") or article.get("contentType")
    if content_type:
        extra["content_type"] = content_type

    return {
        "title": title,
        "raw_text": raw_text,
        "publisher": publisher,
        "link": link,
        "external_id": external_id,
        "timestamp": _parse_yahoo_timestamp(ts_raw),
        "extra": extra or None,
    }


def _base_event(
    *,
    source: str,
    raw_text: str,
    author_id: str,
    timestamp: int,
    external_id: str | None = None,
    metrics: dict[str, Any] | None = None,
    link_meta: dict[str, Any] | None = None,
    language: str | None = None,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    event: dict[str, Any] = {
        "event_id": str(uuid.uuid4()),
        "source": source,
        "raw_text": raw_text,
        "author_id": author_id or "unknown",
        "metrics": metrics or {},
        "timestamp": timestamp,
        "ingested_at": int(datetime.now(timezone.utc).timestamp()),
    }
    if external_id:
        event["external_id"] = external_id
    if link_meta:
        event["link_meta"] = link_meta
    if language:
        event["language"] = language
    if extra:
        event.update(extra)
    return event


def tweet_to_raw_event(tweet: dict[str, Any]) -> dict[str, Any]:
    """Map 1 tweet RapidAPI → schema Stage 1."""
    user = tweet.get("user")
    if isinstance(user, dict):
        author_id = str(user.get("user_id") or user.get("id") or user.get("screen_name") or "")
        followers = user.get("follower_count") or user.get("followers_count")
    else:
        author_id = str(tweet.get("screen_name") or tweet.get("user_username") or "")
        followers = None

    text = tweet.get("text")
    if text is not None:
        text = str(text).replace("\r\n", "\n").replace("\r", "\n")

    likes = tweet.get("favorite_count")
    if likes is None:
        likes = tweet.get("favorites")
    retweets = tweet.get("retweet_count")
    if retweets is None:
        retweets = tweet.get("retweets")

    metrics: dict[str, Any] = {
        "likes": likes or 0,
        "retweets": retweets or 0,
    }
    if followers is not None:
        metrics["followers"] = followers

    created = tweet.get("created_at") or tweet.get("creation_date")
    tweet_id = tweet.get("tweet_id")
    external_id = str(tweet_id) if tweet_id is not None else None

    event = _base_event(
        source="twitter",
        raw_text=text or "",
        author_id=author_id,
        timestamp=_parse_timestamp(str(created) if created else None),
        external_id=external_id,
        metrics=metrics,
    )
    if external_id:
        event["tweet_id"] = external_id
    return event


def news_av_to_raw_event(article: dict[str, Any]) -> dict[str, Any]:
    """Map 1 bài Alpha Vantage NEWS_SENTIMENT → schema Stage 1."""
    title = str(article.get("title") or "").strip()
    summary = str(article.get("summary") or "").strip()
    raw_text = title
    if summary:
        raw_text = f"{title}\n\n{summary}" if title else summary

    authors = article.get("authors")
    if isinstance(authors, list) and authors:
        author_id = ", ".join(str(a) for a in authors if a)
    else:
        author_id = str(article.get("source") or article.get("source_domain") or "news")

    url = str(article.get("url") or "").strip()
    link_meta = {"url": url, "title": title}
    if article.get("source"):
        link_meta["publisher"] = article.get("source")

    return _base_event(
        source="news",
        raw_text=raw_text,
        author_id=author_id,
        timestamp=_parse_timestamp(str(article.get("time_published") or "")),
        external_id=url or None,
        metrics={},
        link_meta=link_meta,
        language="en",
        extra={
            "news_provider": "alpha_vantage",
            "overall_sentiment_score": article.get("overall_sentiment_score"),
            "overall_sentiment_label": article.get("overall_sentiment_label"),
        },
    )


def news_yahoo_to_raw_event(article: dict[str, Any], *, symbol: str) -> dict[str, Any] | None:
    """Map 1 bài yfinance Ticker.news → schema Stage 1. None nếu không có nội dung."""
    normalized = normalize_yahoo_article(article)
    if normalized is None:
        return None

    title = normalized["title"]
    raw_text = normalized["raw_text"]
    publisher = normalized["publisher"]
    link = normalized["link"]
    external_id = normalized["external_id"]
    timestamp = normalized["timestamp"]

    extra: dict[str, Any] = {"news_provider": "yahoo_finance", "related_tickers": [symbol]}
    if normalized.get("extra"):
        extra.update(normalized["extra"])

    return _base_event(
        source="news",
        raw_text=raw_text,
        author_id=publisher,
        timestamp=timestamp,
        external_id=external_id or None,
        metrics={},
        link_meta={"url": link, "title": title, "symbol": symbol},
        language="en",
        extra=extra,
    )


def reddit_to_raw_event(post: dict[str, Any]) -> dict[str, Any]:
    """Map 1 Reddit post listing → schema Stage 1."""
    title = str(post.get("title") or "").strip()
    selftext = str(post.get("selftext") or "").strip()
    raw_text = title
    if selftext and selftext not in ("[removed]", "[deleted]"):
        raw_text = f"{title}\n\n{selftext}" if title else selftext

    author = str(post.get("author") or "unknown")
    subreddit = str(post.get("subreddit") or "")
    external_id = str(post.get("name") or post.get("id") or "")

    metrics: dict[str, Any] = {
        "likes": post.get("ups") or 0,
        "comments": post.get("num_comments") or 0,
    }
    if post.get("upvote_ratio") is not None:
        metrics["upvote_ratio"] = post.get("upvote_ratio")

    link = str(post.get("url") or "").strip()
    link_meta = {"url": link, "title": title}
    if subreddit:
        link_meta["subreddit"] = subreddit

    created = post.get("created_utc")
    if isinstance(created, (int, float)):
        timestamp = int(created)
    else:
        timestamp = int(datetime.now(timezone.utc).timestamp())

    extra: dict[str, Any] = {}
    if subreddit:
        extra["subreddit"] = subreddit
    fetch_mode = post.get("reddit_fetch_mode")
    if fetch_mode:
        extra["reddit_fetch_mode"] = fetch_mode

    return _base_event(
        source="reddit",
        raw_text=raw_text,
        author_id=author,
        timestamp=timestamp,
        external_id=external_id or None,
        metrics=metrics,
        link_meta=link_meta,
        language="en",
        extra=extra or None,
    )
