# Ingest — Stage 1 (Raw Collection)

Thu thập raw social events từ **nhiều nguồn** và lưu **MongoDB Atlas** theo schema Stage 1 trong [`docs/pipeline-overview.md`](../../docs/pipeline-overview.md).

**Cơ sở lý thuyết:** [`docs/theory/ingest.md`](../../docs/theory/ingest.md)

## Nguồn hỗ trợ

| Lệnh | `source` | API / thư viện | API key |
| --- | --- | --- | --- |
| `twitter` | `twitter` | RapidAPI twitter154 | `RAPIDAPI_KEY` |
| `news-av` | `news` | Alpha Vantage `NEWS_SENTIMENT` | `ALPHA_VANTAGE_API_KEY` |
| `news-yahoo` | `news` | `yfinance` (Yahoo Finance) | Không |
| `reddit` | `reddit` | Reddit OAuth API hoặc **Playwright** (`--browser`) | OAuth *hoặc* `uv sync --extra browser` |
| `all` | — | Chạy mọi nguồn có key | Tuỳ nguồn |

## Cấu trúc

```text
playground/ingest/
├── .env.example
├── run.py
└── lib/
    ├── config.py
    ├── events.py          # map API → raw event contract
    ├── mongo.py
    └── collectors/
        ├── twitter.py
        ├── news_av.py
        ├── news_yahoo.py
        └── reddit.py
```

## Document mẫu

### Twitter

```json
{
  "event_id": "550e8400-e29b-41d4-a716-446655440000",
  "source": "twitter",
  "external_id": "1234567890",
  "tweet_id": "1234567890",
  "raw_text": "Buy $BTC now...",
  "author_id": "BitcoinMagazine",
  "metrics": { "likes": 749, "retweets": 113, "followers": 3200000 },
  "timestamp": 1714248653,
  "ingested_at": 1716110997
}
```

### News (Alpha Vantage / Yahoo)

```json
{
  "event_id": "...",
  "source": "news",
  "external_id": "09479ec0-2158-4b6c-96ce-aecb94ee78ca",
  "raw_text": "Why Michael Saylor's $2.5M bitcoin sale is turning heads\n\nYahoo Finance Senior Report...",
  "author_id": "Yahoo Finance Video",
  "link_meta": { "url": "https://finance.yahoo.com/video/...", "title": "...", "symbol": "BTC-USD" },
  "news_provider": "yahoo_finance",
  "content_type": "VIDEO",
  "timestamp": 1714248653,
  "ingested_at": 1716110997
}
```

Yahoo qua `yfinance`: API mới trả `{ id, content: { title, summary, pubDate, ... } }` — ingest tự chuẩn hóa; bài không có title/summary bị bỏ qua.

### Reddit

```json
{
  "event_id": "...",
  "source": "reddit",
  "external_id": "t3_abc123",
  "raw_text": "Post title\n\nBody...",
  "author_id": "crypto_user",
  "metrics": { "likes": 120, "comments": 45 },
  "link_meta": { "url": "...", "subreddit": "cryptocurrency" },
  "subreddit": "cryptocurrency",
  "timestamp": 1714248653,
  "ingested_at": 1716110997
}
```

Dedup MongoDB: unique sparse trên `(source, external_id)`; tweet vẫn có thêm index `tweet_id` để tương thích bản ghi cũ.

## Setup

```bash
cd playground/ingest
cp .env.example .env
# Điền MONGODB_URI + key tuỳ nguồn bạn dùng
uv sync
```

## Chạy

```bash
# Twitter (mặc định trước đây)
uv run python run.py twitter

# Tin Alpha Vantage
uv run python run.py news-av --tickers "CRYPTO:BTC,CRYPTO:ETH" --limit 20

# Tin Yahoo gắn mã crypto
uv run python run.py news-yahoo --symbol ETH-USD

# Reddit — API (OAuth) hoặc browser
uv run python run.py reddit --subreddit cryptocurrency --limit 25
uv run python run.py reddit --subreddit Bitcoin --listing hot

# Reddit qua Playwright (khi API 403 — có thể vẫn bị "network security")
uv sync --extra browser
uv run playwright install chromium
# Bước 1: đăng nhập thủ công, lưu session (vượt captcha trong browser)
uv run python run.py reddit --browser --login
# Bước 2: scrape với session đã lưu
uv run python run.py reddit --browser --listing new --limit 10 --dry-run
```

### Reddit bị chặn ("network security")

Reddit chặn bot theo **IP + fingerprint**, không chỉ thiếu OAuth. Browser automation **không đảm bảo** vượt được block.

| Cách | Ghi chú |
| --- | --- |
| **OAuth API** (không `--browser`) | Ổn định nhất — điền `REDDIT_CLIENT_*` + username/password |
| **`--browser --login`** | Đăng nhập tay 1 lần → lưu `.reddit_session.json` |
| **Đổi mạng** | Tắt VPN; thử 4G/home thay mạng trường/datacenter |
| **Bỏ Reddit tạm** | MVP vẫn chạy với `twitter`, `news-av`, `news-yahoo` |

```bash
# Mọi nguồn trừ Reddit (mặc định)
uv run python run.py all
# Có Reddit: uv run python run.py all --with-reddit

# Chỉ fetch, không ghi DB
uv run python run.py reddit --dry-run
uv run python run.py news-yahoo --dry-run

# Tắt progress chi tiết
uv run python run.py reddit -q
```

Khi chạy bình thường, CLI in tiến độ theo từng bước (gọi API, xử lý bản ghi, ghi MongoDB). Terminal hỗ trợ TTY sẽ hiện progress bar dạng `[=====>-----------] 5/20 (25%)`.

## Biến môi trường

File **`playground/ingest/.env`** gom key từ mọi playground có dùng API (X-API, alpha_vantage, …). Các playground khác không có `.env` riêng — chỉ `export` hoặc dùng chung file này.

| Biến | Playground nguồn | Bắt buộc | Mô tả |
| --- | --- | --- | --- |
| `MONGODB_URI` | ingest | Có (khi ghi DB) | Connection string Atlas |
| `MONGODB_DB` | ingest | Không | Mặc định `crypto_mvp` |
| `MONGODB_COLLECTION` | ingest | Không | Mặc định `raw_events` |
| `RAPIDAPI_KEY` | `playground/X-API` | Cho `twitter` | Key RapidAPI twitter154 |
| `ALPHA_VANTAGE_API_KEY` | `playground/alpha_vantage` | Cho `news-av` | Key Alpha Vantage |
| `REDDIT_USER_AGENT` | ingest | Khuyến nghị | Format `linux:app:v0.1 (by /u/username)` |
| `REDDIT_CLIENT_ID` | ingest | **Cho reddit** | OAuth app — id dưới tên app |
| `REDDIT_CLIENT_SECRET` | ingest | **Cho reddit** | OAuth secret (script app) |
| `REDDIT_USERNAME` | ingest | **Cho reddit** | Tài khoản Reddit chạy script |
| `REDDIT_PASSWORD` | ingest | Cho API reddit | Mật khẩu hoặc app password |
| `REDDIT_BROWSER_HEADLESS` | ingest | Không | `false` = mở cửa sổ Chromium khi debug |
| — | `playground/yahoo_finance` | Không | `news-yahoo` qua yfinance, không key |
| — | `playground/finetune/fasttext` | Không | Train local, không key |

## Bước tiếp theo (pipeline)

- **Stage 2:** `playground/filter` — đọc `raw_events`, cascade L1/L2/L3 → `clean_events`
- **Stage 3:** `playground/ner` — map `coin_id`, fan-out → `mapped_events` (hybrid / validator / full + OpenRouter)
- Worker daemon + push **Kafka** `topic_raw_events`
- Thêm nguồn **CCXT** OHLCV (nhánh market, schema riêng)
