# Playground Alpha Vantage — crypto / digital currency

`run.py` chỉ gọi endpoint phù hợp **tiền mã hóa và tỉ giá** (không còn OVERVIEW cổ phiếu, TIME_SERIES cổ phiếu, RSI cổ phiếu).

## Biến môi trường

```bash
export ALPHA_VANTAGE_API_KEY="..."
```

Chỉ cần Python stdlib (`urllib`).

```bash
cd playground/alpha_vantage
python run.py --help
```

Mặc định output: **`alphavantage_response.json`**, **`alphavantage_response.md`**.

## Subcommands

| Lệnh | `function` Alpha Vantage | Ý nghĩa |
|------|--------------------------|---------|
| **exchange-rate** | `CURRENCY_EXCHANGE_RATE` | Tỉ giá thời điểm hiện tại giữa hai mã (`--from-ccy BTC` → `--to-ccy USD`). |
| **crypto-daily** | `DIGITAL_CURRENCY_DAILY` | Chuỗi giá **theo ngày** (BTC/ETH… quy đổi vào `market` USD, USDT…). |
| **crypto-weekly** | `DIGITAL_CURRENCY_WEEKLY` | Tương tự theo **tuần**. |
| **crypto-monthly** | `DIGITAL_CURRENCY_MONTHLY` | Tương tự theo **tháng**. |
| **crypto-intraday** | `CRYPTO_INTRADAY` | OHLCV **trong ngày** (1m … 60m) + `outputsize` compact/full. |
| **news** | `NEWS_SENTIMENT` | Tin và sentiment; ticker mặc định `CRYPTO:BTC` (định dạng AV khuyến nghị cho crypto). |

### Options chung (mọi subcommand)

| Option | Ý nghĩa |
|--------|---------|
| `--json-out` | Đường dẫn file envelope JSON (request đã ẩn key + response). |
| `--md-out` | File Markdown đọc nhanh. |
| `--no-save` | Chỉ stdout. |

### Tham số đặc thù

- **exchange-rate:** `--from-ccy`, `--to-ccy` (mặc định `BTC`/`USD`).
- **crypto-* (daily/weekly/monthly):** `--symbol` (vd. BTC), `--market` (vd. USD).
- **crypto-intraday:** `--symbol`, `--market`, `--interval` (5min, …), `--outputsize` compact|full.
- **news:** `--tickers` (vd. `CRYPTO:BTC,CRYPTO:ETH`), `--topics` (tuỳ chọn), `--days`, `--limit`.

### Ý nghĩa dữ liệu trả về

- **Digital currency time series:** thường có open / high / low / close và volume trong schema JSON Alpha Vantage — OHLC là **giá thị trường được chọn**, `market` là đơn vị định giá.
- **INTRADAY:** mật độ nến cao — gần realtime, thích hợp biểu đồ ngắn hạn (tốn quota API).
- **NEWS_SENTIMENT:** có thể kèm score/label tin — dùng cho **tone** thị trường, không phải tín hiệu vào lệnh thuần.

Tài liệu gốc: [alphavantage.co/documentation](https://www.alphavantage.co/documentation/) (Crypto, FX, Digital Currency).

## Ví dụ

```bash
python run.py exchange-rate --from-ccy ETH --to-ccy EUR
python run.py crypto-daily --symbol BTC --market USD
python run.py crypto-intraday --symbol ETH --market USD --interval 5min --outputsize compact
python run.py news --tickers CRYPTO:BTC --days 3 --limit 15
```

Nếu response có trường `Information` (rate limit / premium), chờ hoặc nâng gói trên Alpha Vantage.

### Lỗi `Connection reset` / không kết nối được

Client đã **thử lại 4 lần** với backoff. Nếu vẫn lỗi: thường do **firewall**, **VPN**, **mạng nội bộ**, hoặc chặn SSL. Thử máy khác/mạng khác hoặc `curl -sI https://www.alphavantage.co/` để kiểm tra HTTPS.
