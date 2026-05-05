# Playground Yahoo Finance (`yfinance`) — ưu tiên crypto

Dữ liệu lấy qua **`yfinance`** từ Yahoo Finance (Không là API Yahoo chính thức). **Ticker crypto trên Yahoo** thường là `BTC-USD`, `ETH-USD`, `SOL-USD`, … (cặp có dấu gạch).

## Cài đặt

```bash
cd playground/yahoo_finance
python -m venv .venv && .venv/bin/pip install -r requirements.txt
```

Mặc định ghi **`yahoo_finance_response.json`** + **`yahoo_finance_response.md`**.

## Options chung

| Option | Ý nghĩa |
|--------|---------|
| `--json-out` | Envelope đầy đủ (`command`, `request_descriptor`, `response`). |
| `--md-out` | Bản Markdown. |
| `--no-save` | Chỉ in terminal. |

## Subcommands — mặc định `BTC-USD` (trừ `ticker`)

| Lệnh | Mặc định | Đại ý |
|------|----------|--------|
| **fast-info** | `--symbol BTC-USD` | Giá/metadata gọn (phụ thuộc Yahoo). |
| **history** | `BTC-USD`, `period=1mo`, `interval=1d` | Chuỗi OHLCV — `period`/`interval` giống tài liệu yfinance. |
| **info** | `BTC-USD` | Dict metadata lớn (khác cổ phiếu: ít P/E “công ty”, nhiều field thị trường). |
| **news** | `BTC-USD` | Tin gắn ticker. |
| **ticker** | Không truyền `--symbols` → `BTC-USD ETH-USD SOL-USD` | Gộp `.info` + `.history` cho nhiều mã. |

### ý nghĩa cột `history` (điển hình)

- **Open / High / Low / Close**: biên độ nến theo `interval`.
- **Volume**: khối lượng (đơn vị theo Yahoo).
- Có thể có cột phụ (chia tách, dividend — với crypto thường 0 hoặc không dùng).

### `period` / `interval` gợi ý

- `period`: `1d`, `5d`, `1mo`, `3mo`, `1y`, …
- `interval`: `1m` (chỉ cửa sổ ngắn), `1h`, `1d`, …

## Ví dụ

```bash
.venv/bin/python run.py fast-info
.venv/bin/python run.py history --symbol ETH-USD --period 14d --interval 1h
.venv/bin/python run.py ticker --symbols DOGE-USD PEPE-USD
```

Thư viện: [yfinance](https://github.com/ranaroussi/yfinance).
