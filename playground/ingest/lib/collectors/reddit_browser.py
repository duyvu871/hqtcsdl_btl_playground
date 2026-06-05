"""Reddit qua Playwright — scrape old.reddit.com (session đăng nhập thủ công)."""

from __future__ import annotations

import os
import re
import urllib.parse
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Any

from lib.config import reddit_browser_headless, reddit_browser_storage_path
from lib.events import reddit_to_raw_event

if TYPE_CHECKING:
    from lib.progress import Progress

OLD_REDDIT = "https://old.reddit.com"
REDDIT_HOME = "https://www.reddit.com"

_BLOCK_MARKERS = (
    "blocked by network security",
    "you've been blocked",
    "you have been blocked",
    "cf-browser-verification",
    "challenge-platform",
)

_BLOCK_HELP = """
Reddit chặn truy cập tự động ("network security") — thường do IP (VPN, mạng trường, datacenter).

Cách xử lý (theo thứ tự ưu tiên):
  1. OAuth API (ổn định nhất): điền REDDIT_CLIENT_ID/SECRET/USERNAME/PASSWORD → chạy không --browser
  2. Đăng nhập thủ công 1 lần: uv run python run.py reddit --browser --login
     (mở browser, đăng nhập + vượt captcha nếu có, session lưu vào .reddit_session.json)
  3. Thử mạng khác (4G/home WiFi, tắt VPN)
  4. Tạm bỏ Reddit — dùng twitter + news-av + news-yahoo cho MVP
"""


def _build_url(
    *,
    subreddit: str,
    listing: str,
    query: str,
    sort: str,
) -> str:
    sub = subreddit.strip().lstrip("r/") or "cryptocurrency"
    if listing == "search":
        params = urllib.parse.urlencode(
            {
                "q": query,
                "restrict_sr": "on",
                "sort": sort,
                "t": "all",
            }
        )
        return f"{OLD_REDDIT}/r/{sub}/search?{params}"
    return f"{OLD_REDDIT}/r/{sub}/{listing}/"


def _parse_score(text: str) -> int:
    m = re.search(r"(-?\d+)", text.replace(",", ""))
    return int(m.group(1)) if m else 0


def _parse_comments(text: str) -> int:
    m = re.search(r"(\d+)\s+comment", text, re.I)
    return int(m.group(1)) if m else 0


def _parse_timestamp(iso_value: str | None) -> int:
    if not iso_value:
        return int(datetime.now(timezone.utc).timestamp())
    try:
        dt = datetime.fromisoformat(iso_value.replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp())
    except ValueError:
        return int(datetime.now(timezone.utc).timestamp())


def _ensure_not_blocked(page: Any) -> None:
    try:
        body = page.inner_text("body").lower()
    except Exception:
        body = page.content().lower()
    if any(marker in body for marker in _BLOCK_MARKERS):
        raise RuntimeError(f"Reddit network security block.{_BLOCK_HELP}")


def _browser_context(browser: Any, *, storage_path: Path | None):
    kwargs: dict[str, Any] = {
        "user_agent": (
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36"
        ),
        "viewport": {"width": 1366, "height": 768},
        "locale": "en-US",
    }
    if storage_path and storage_path.is_file():
        kwargs["storage_state"] = str(storage_path)

    context = browser.new_context(**kwargs)
    context.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', { get: () => undefined });"
    )
    return context


def _scrape_page(page: Any, *, subreddit: str, limit: int) -> list[dict[str, Any]]:
    _ensure_not_blocked(page)

    posts: list[dict[str, Any]] = []
    sub = subreddit.strip().lstrip("r/") or "cryptocurrency"
    elements = page.locator("div.thing.link").all()

    if not elements:
        _ensure_not_blocked(page)
        return []

    for el in elements[:limit]:
        fullname = el.get_attribute("data-fullname") or ""
        post_id = fullname.replace("t3_", "") if fullname.startswith("t3_") else fullname

        title = ""
        title_loc = el.locator("a.title")
        if title_loc.count():
            title = title_loc.first.inner_text().strip()
            post_url = title_loc.first.get_attribute("href") or ""
        else:
            post_url = ""

        author = "unknown"
        author_loc = el.locator("a.author")
        if author_loc.count():
            author = author_loc.first.inner_text().strip()

        score = 0
        score_loc = el.locator("div.score.unvoted, div.score.likes, div.score.dislikes")
        if score_loc.count():
            score = _parse_score(score_loc.first.inner_text())

        comments = 0
        comments_loc = el.locator("a.comments")
        if comments_loc.count():
            comments = _parse_comments(comments_loc.first.inner_text())

        created_iso = None
        time_loc = el.locator("time")
        if time_loc.count():
            created_iso = time_loc.first.get_attribute("datetime")

        posts.append(
            {
                "name": fullname or f"t3_{post_id}",
                "id": post_id,
                "title": title,
                "selftext": "",
                "author": author,
                "subreddit": sub,
                "ups": score,
                "num_comments": comments,
                "created_utc": _parse_timestamp(created_iso),
                "url": post_url,
            }
        )

    return posts


def save_reddit_browser_session(*, progress: Progress | None = None) -> Path:
    """Mở browser headed — user đăng nhập Reddit, lưu cookies/localStorage."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Thiếu Playwright. Chạy: uv sync --extra browser && uv run playwright install chromium"
        ) from e

    storage_path = reddit_browser_storage_path()
    if progress:
        progress.log(f"Reddit login: mở browser → {REDDIT_HOME}")
        progress.log(f"Session sẽ lưu tại {storage_path}")

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=False,
            args=["--disable-dev-shm-usage"],
        )
        try:
            context = _browser_context(browser, storage_path=None)
            page = context.new_page()
            page.goto(REDDIT_HOME, wait_until="domcontentloaded", timeout=90_000)
            print(
                "\n>>> Đăng nhập Reddit trong cửa sổ browser "
                "(vượt captcha / network security nếu có).\n"
                ">>> Xong thì quay lại terminal và nhấn Enter để lưu session...\n",
                flush=True,
            )
            input()
            _ensure_not_blocked(page)
            storage_path.parent.mkdir(parents=True, exist_ok=True)
            context.storage_state(path=str(storage_path))
        finally:
            browser.close()

    if progress:
        progress.log(f"Đã lưu session → {storage_path}")
    return storage_path


def collect_reddit_browser_events(
    *,
    subreddit: str = "cryptocurrency",
    query: str = "bitcoin OR ethereum OR BTC OR ETH",
    sort: str = "new",
    limit: int = 25,
    listing: str = "search",
    progress: Progress | None = None,
) -> list[dict[str, Any]]:
    try:
        from playwright.sync_api import sync_playwright
    except ImportError as e:
        raise RuntimeError(
            "Thiếu Playwright. Chạy:\n"
            "  uv sync --extra browser\n"
            "  uv run playwright install chromium"
        ) from e

    url = _build_url(subreddit=subreddit, listing=listing, query=query, sort=sort)
    lim = max(1, min(100, limit))
    storage_path = reddit_browser_storage_path()
    headless = reddit_browser_headless()
    if not os.getenv("DISPLAY"):
        headless = True

    if progress:
        progress.log(f"Reddit browser: mở {url}")
        progress.log(f"Reddit browser: headless={headless}")
        if storage_path.is_file():
            progress.log(f"Reddit browser: dùng session {storage_path.name}")
        else:
            progress.log(
                "Reddit browser: chưa có session — chạy `reddit --browser --login` nếu bị block"
            )

    raw_posts: list[dict[str, Any]] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(
                headless=headless,
                args=["--disable-dev-shm-usage", "--no-sandbox"],
            )
            try:
                context = _browser_context(
                    browser,
                    storage_path=storage_path if storage_path.is_file() else None,
                )
                page = context.new_page()
                if progress:
                    progress.log("Reddit browser: đang tải trang...")
                page.goto(url, wait_until="domcontentloaded", timeout=90_000)
                _ensure_not_blocked(page)
                page.wait_for_selector("div.thing.link", timeout=30_000)
                raw_posts = _scrape_page(page, subreddit=subreddit, limit=lim)
            finally:
                browser.close()
    except RuntimeError:
        raise
    except Exception as e:
        raise RuntimeError(
            f"Reddit browser thất bại: {e}\n"
            "Gợi ý: reddit --browser --login hoặc dùng OAuth (bỏ --browser)."
        ) from e

    events: list[dict[str, Any]] = []
    total = len(raw_posts)
    if progress:
        progress.log(f"Reddit browser: map {total} post → raw event...")

    for i, post in enumerate(raw_posts, start=1):
        events.append(
            reddit_to_raw_event(
                {
                    **post,
                    "reddit_fetch_mode": "browser",
                }
            )
        )
        if progress:
            progress.bar(i, total, prefix="Reddit browser: ")

    if progress:
        progress.log(f"Reddit browser: {len(events)} event(s).")

    return events
