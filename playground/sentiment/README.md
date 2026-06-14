# 🌌 Galaxy Score™: Hệ thống Đánh giá Định lượng & Phân tích Phân kỳ Tài sản Crypto

Một hệ thống phát sinh tín hiệu giao dịch và đánh giá tài sản định lượng tiên tiến, hiệu suất cao dành riêng cho thị trường tiền mã hóa. Ứng dụng mô hình kiến trúc **MVC (Model-View-Controller)** và được xây dựng trên thư viện xử lý dữ liệu siêu tốc **Polars**, hệ thống này xử lý các tập dữ liệu thay thế đa phương thức (tâm lý mạng xã hội, khối lượng tương tác) kết hợp với các chỉ số thị trường truyền thống (biến thiên giá) nhằm phát hiện các điểm phân kỳ bất thường mang lại lợi thế giao dịch.

---

## 📊 1. Tổng quan Dự án & Cấu trúc Thư mục

Hệ thống **Galaxy Score™** giải quyết một thách thức lớn trong tài chính định lượng hiện đại: sự đồng bộ hóa và tổng hợp các dữ liệu thay thế đa chiều, không đồng bộ với dữ liệu giá thị trường tần suất cao. Bằng cách chuyển đổi dữ liệu mạng xã hội và tín hiệu giá thô thành một không gian vectơ chuẩn hóa thông qua các phép đo thống kê cuộn (rolling statistics), hệ thống tính toán một thước đo phân kỳ/hội tụ tổng hợp để cô lập các điểm kém hiệu quả của thị trường.

### Chi tiết các Module:
* **`lib/prep.py` [Model - Tiền xử lý Dữ liệu]:** Xử lý việc căn chỉnh chuỗi thời gian thông qua phép kết nối (inner joins) tối ưu trên các chiều `timestamp` và `coin_id`. Tính toán tỷ suất lợi nhuận giá liên tục thông qua kỹ thuật độ trễ (lag-shifting).
* **`lib/score.py` [Model - Logic Toán học]:** Thực thi các phép chuẩn hóa vectơ cuộn và đóng gói hệ thống tổng hợp hàm sigmoid phi tuyến tính độc quyền.
* **`lib/rules.py` [Controller - Quy tắc Giao dịch]:** Triển khai một hệ thống ánh xạ ranh giới nghiêm ngặt để kiểm tra các đặc tính toán học so với các vùng đuôi thống kê cực đoan nhằm phát cảnh báo hành động.
* **`main.py` [View / Điều phối Hệ thống]:** Đóng vai trò là bối cảnh thực thi hệ thống và thành phần hiển thị bảng điều khiển ở cấp độ dòng lệnh (terminal).
* **`config.py` & `connectors.py`:** Quản lý biến môi trường và thiết lập luồng kết nối luân chuyển dữ liệu thực tế (Kafka/Redpanda, TimescaleDB, MongoDB).

---

## 🎓 2. Cơ sở Lý luận & Khung Toán học

Điểm khác biệt cốt lõi của **Galaxy Score™** so với các bộ dao động (oscillators) thông thường là toàn bộ luồng tính toán đều được tham chiếu từ các mô hình kinh tế lượng tài chính đã được chứng minh. Hệ thống vận hành qua 3 giai đoạn toán học chính:

### Giai đoạn 1: Chuẩn hóa Vectơ Cuộn (Z-Score Normalization)
**Vấn đề:** Khối lượng mạng xã hội (`social_volume`) có giá trị hàng chục nghìn, trong khi lợi nhuận giá (`price_change_pct`) chỉ ở mức phần trăm nhỏ ($0.01$). Không thể cộng trừ trực tiếp các giá trị khác biệt về mặt thứ nguyên này.
**Cơ sở học thuật:** Theo nghiên cứu của **Tetlock (2007)** [[DOI: 10.1111/j.1540-6261.2007.01232.x](https://doi.org/10.1111/j.1540-6261.2007.01232.x)], để cô lập tín hiệu thực sự khỏi "nhiễu trắng" (white noise) của thị trường, các chỉ số đo lường tâm lý cần được chuẩn hóa so với trung bình lịch sử gần nhất của chính nó.

Hệ thống áp dụng công thức Z-score cuộn (rolling Z-score) để đưa tất cả luồng dữ liệu về cùng một phân phối chuẩn hóa (Standardized Distribution):

$$Z(X_t) = \frac{X_t - \mu_{\tau}(X_t)}{\sigma_{\tau}(X_t)}$$

**Chú giải biến số:**
* $X_t$: Giá trị quan sát thô của luồng dữ liệu tại thời điểm $t$ (ví dụ: điểm sentiment, volume).
* $\tau$: Kích thước cửa sổ thời gian cuộn (rolling window size), dùng để đánh giá tính lịch sử cục bộ (trong hệ thống đang thiết lập mặc định $\tau = 24$ giờ).
* $\mu_{\tau}(X_t)$: Giá trị trung bình mẫu (Rolling Mean) của chuỗi dữ liệu $X$ được tính trong khoảng thời gian $\tau$ ngay trước thời điểm $t$.
* $\sigma_{\tau}(X_t)$: Độ lệch chuẩn mẫu (Rolling Standard Deviation) của chuỗi $X$ được tính trong khoảng thời gian $\tau$.
* $Z(X_t)$: Giá trị đã được chuẩn hóa (Z-score) tại thời điểm $t$, thể hiện khoảng cách từ giá trị hiện tại đến mức trung bình tính bằng số lần độ lệch chuẩn. Giá trị này không có thứ nguyên (dimensionless).

---

### Giai đoạn 2: Trích xuất Hệ số Phân kỳ ($C_t$)
**Vấn đề:** Làm sao để định lượng được sự chênh lệch khi mạng xã hội đang "FOMO" (tích cực) nhưng giá lại đang giảm?
**Cơ sở học thuật:** Dựa trên nền tảng của **Bollen et al. (2011)** [[DOI: 10.1016/j.jocs.2010.12.002](https://doi.org/10.1016/j.jocs.2010.12.002)] chứng minh mạng xã hội là "chỉ báo dẫn dắt" đi trước giá, và mô hình đánh giá tổng hợp F-Score của **Piotroski (2000)** [[DOI: 10.2307/2672906](https://doi.org/10.2307/2672906)], hệ thống tính toán một hệ số hội tụ/phân kỳ tổng hợp bằng cách gán trọng số có hướng. Điểm mấu chốt là **trừ đi** vectơ giá trị lợi nhuận.

$$C_t = w_1 Z_{\text{sentiment}} + w_2 Z_{\text{volume}} - w_3 Z_{\text{price\_return}}$$

**Chú giải biến số:**
* $C_t$: Hệ số phân kỳ (Divergence Coefficient) cốt lõi tại thời điểm $t$.
* $w_1, w_2, w_3$: Các siêu tham số trọng số (Hyperparameter weights) được gán để kiểm soát mức độ đóng góp của từng chỉ báo vào điểm tổng hợp (hệ thống thiết lập mặc định $w_1=1.0, w_2=0.5, w_3=1.0$).
* $Z_{\text{sentiment}}$: Biến thiên chuẩn hóa của cường độ tâm lý người dùng.
* $Z_{\text{volume}}$: Biến thiên chuẩn hóa của khối lượng thảo luận xã hội.
* $Z_{\text{price\_return}}$: Biến thiên chuẩn hóa của tỷ suất lợi nhuận giá trị tài sản. 
*(Lưu ý dấu trừ trước $w_3$: Khi $Z_{\text{sentiment}}$ dương mạnh nhưng $Z_{\text{price\_return}}$ âm mạnh, phép trừ biến thành cộng, làm $C_t$ bùng nổ vọt lên, định lượng chính xác được sự "phân kỳ").*

---

### Giai đoạn 3: Ánh xạ Sigmoid (Non-linear Mapping) & Hành động
**Vấn đề:** $C_t$ nằm trong khoảng $(-\infty, +\infty)$, khó để con người diễn giải trên các bảng điều khiển (Dashboard) và khó làm đầu vào cho các mô hình AI sau này.
**Cơ sở học thuật:** Để chuẩn bị dữ liệu đầu vào cho các kiến trúc học sâu dự báo chuỗi thời gian như Temporal Fusion Transformers theo **Lim et al. (2021)** [[DOI: 10.1016/j.ijforecast.2021.03.012](https://doi.org/10.1016/j.ijforecast.2021.03.012)], dữ liệu cần được đưa về một không gian xác suất bị chặn. 

Hệ thống sử dụng hàm kích hoạt Logistic (Sigmoid Curve) để nén các biến động thông thường ở vùng trung tâm và kéo giãn các biến động cực đại ở hai đầu biên, ép miền giá trị về thang chuẩn $0 \dots 100$:

$$\text{Galaxy Score™} = \frac{100.0}{1.0 + e^{-C_t}}$$

**Chú giải biến số:**
* $\text{Galaxy Score™}$: Điểm số cuối cùng, đại diện cho sức mạnh xu hướng/phân kỳ của tài sản, nằm gọn trong tập $[0, 100]$.
* $100.0$: Hệ số nhân đồ thị (Scaling factor) để chuyển đổi vùng $[0, 1]$ của hàm Sigmoid gốc sang thang điểm phần trăm trực quan.
* $e$: Hằng số Euler (cơ số của logarit tự nhiên, $e \approx 2.71828$).
* $C_t$: Hệ số phân kỳ tổng hợp lấy từ Giai đoạn 2.

Tại `lib/rules.py`, các ngưỡng giới hạn (Thresholds) được thiết lập tại vùng đuôi phân phối (extreme tails) của $\text{Galaxy Score™}$ để phát tín hiệu:
* **$\text{Score} \ge 80.0$:** Bullish Divergence $\rightarrow$ **BUY** (Tâm lý xã hội cực tốt áp đảo đà giảm giá).
* **$\text{Score} \le 20.0$:** Bearish Divergence $\rightarrow$ **SELL** (FUD lan rộng bất chấp giá đang giữ vững).
* **$20.0 < \text{Score} < 80.0$:** Định nghĩa trạng thái cân bằng $\rightarrow$ **HOLD**.

---

## 📂 3. Hiện thực hóa bằng Mã nguồn (Data Prep & Score Core)

Sự kết hợp giữa công thức kinh tế lượng và kỹ thuật lập trình hiệu năng cao được thể hiện rõ qua lõi Polars. Thay vì tính toán từng hàng (row-by-row), toàn bộ khung toán học trên được thực thi bằng biểu thức song song (Vectorized Expressions):

### 3.1. Xử lý Dữ liệu thô (`lib/prep.py`)
```python
def prepare_scoring_data(market_data: list[dict], social_data: list[dict]) -> pl.DataFrame:
    df_market = pl.DataFrame(market_data).with_columns(pl.col("timestamp").str.to_datetime())
    df_social = pl.DataFrame(social_data).with_columns(pl.col("timestamp").str.to_datetime())
    
    df = df_market.join(df_social, on=["timestamp", "coin_id"], how="inner").sort("timestamp")
    
    df = df.with_columns(
        price_change_pct=(pl.col("close") - pl.col("close").shift(1)) / pl.col("close").shift(1)
    )
    return df.drop_nulls()