"""Collectors Stage 1 — mỗi hàm trả list[dict] raw_events sẵn sàng ghi MongoDB."""

from src.pipeline.ingest.collectors.news_av import collect_news_av_events
from src.pipeline.ingest.collectors.news_yahoo import collect_news_yahoo_events
from src.pipeline.ingest.collectors.reddit import collect_reddit_events
from src.pipeline.ingest.collectors.twitter import DEFAULT_QUERY, collect_twitter_events

__all__ = [
    "DEFAULT_QUERY",
    "collect_twitter_events",
    "collect_news_av_events",
    "collect_news_yahoo_events",
    "collect_reddit_events",
]
