# Playground X (Twitter) search — RapidAPI twitter154 (ưu tiên crypto / thị trường)

Script `run.py` gọi endpoint search của RapidAPI (**twitter154**), có thể lấy thêm trang nhờ `continuation_token`, rồi xuất **JSON** và tùy chọn **Markdown**. Query mặc định (`--query`) xoay quanh **Bitcoin, Ethereum, macro, ETF, halving** — có thể đổi sang meme coin / altcoin nếu cần.

## Yêu cầu

```bash
export RAPIDAPI_KEY="..."
```

Không cần cài package Python thêm (chỉ **stdlib**: `urllib`).

Chạy từ thư mục này hoặc trỏ đường dẫn đầy đủ đến `run.py`:

```bash
cd playground/X-API
python run.py --help
```

File JSON mặc định: **`search_results.json`** (cạnh `run.py`).

## Options chính

| Option | Mặc định | Ý nghĩa |
|--------|----------|---------|
| `--query` | Câu hỏi dài (crypto + macro/ETF/…) | Toán tử tìm kiếm của X (OR, AND, … tuỳ API). |
| `--section` `top` \| `latest` | `top` | `top`: thường highlight; `latest`: mới nhất, thường ồn hơn. |
| `--min-likes` | 50 | Ngưỡng tối thiểu likes (lọc spam/bài yếu). Tăng → ít kết quả hơn nhưng hay “chất” hơn. |
| `--min-retweets` | 10 | Ngưỡng retweet (độ lan). |
| `--min-replies` | 5 | Ưu tiên thread có tranh luận. Đặt `0` để tắt sàn này (code coi `≤0` = không gửi). |
| `--limit` | 15 | Số tweet mỗi **request** (1–20). |
| `--max-pages` | 3 | Số lần gọi API tối đa (phân trang bằng `continuation_token`). |
| `--recency-days` | 14 | Nếu **không** có `--start-date` và không `--no-recency-filter`: chỉ lấy từ ngày (UTC) = hôm nay − N. |
| `--start-date` | — | `YYYY-MM-DD` — cửa sổ từ (ghi đè `--recency-days`). |
| `--end-date` | — | `YYYY-MM-DD` — cửa sổ đến. |
| `--no-recency-filter` | — | Không gửi `start_date` (full range theo API). |
| `--language` | `en` | Ngôn ngữ nếu API hỗ trợ. |
| `--max-per-user` | 2 | Tối đa bao nhiêu tweet / `@user` trong kết quả cuối (tránh một nick tràn file). Đặt `0` = không giới hạn. |
| `-o`, `--out` | `search_results.json` | Đường dẫn JSON (mặc định **cùng thư mục với `run.py`**). |
| `-m`, `--markdown` | tắt | Ghi thêm `.md` cùng stem với `-o` (vd. `out.json` → `out.md`). |
| `--md-out PATH` | — | Ghi Markdown vào file cụ thể (không cần `-m`). |

## Cấu trúc file JSON

- **`results`**: mỗi phần tử là một tweet đã rút gọn:
  - **`user`**: `screen_name` / handle (hiển thị nguồn).
  - **`text`**: nội dung tweet.
  - **`favorite_count`**: số lượt thích (proxy mức đồng thuận/chú ý).
  - **`retweet_count`**: số lượt retweet (proxy lan truyền).
  - **`created_at`**: thời điểm (chuỗi theo API).
- **`continuation_token`**: nếu còn (và bạn chưa hết `max-pages`), có thể dùng để trang tiếp theo ở phía server — script đã tự gọi lặp theo `max-pages`.
- **`filters`**: snapshot tham số đã dùng (để replay / debug).
- **`pages_fetched`**: số lần gọi API thực tế.

**Lưu ý:** API **không** trả `impressions/views` trong output rút gọn này; nếu cần reach, phải mở rộng schema từ raw response.

## Markdown

File `.md` gồm bảng filter + từng tweet (thời gian, likes, retweets, nội dung trong block code). Phù hợp đọc nhanh hoặc đưa vào agent.

## Ví dụ

```bash
python run.py -o search_results.json -m
python run.py --query "bitcoin ETF" --min-likes 100 --max-pages 2
python run.py --md-out report.md --no-recency-filter
```
