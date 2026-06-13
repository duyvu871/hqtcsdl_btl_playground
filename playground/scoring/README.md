# Hệ Thống Định Lượng Galaxy Score 


## Bản Đồ Ánh Xạ Toán Học & Cấu Trúc Mã Nguồn (Math-to-Code Mapping)

Dưới đây là bảng đối soát chi tiết quy định công thức toán học nào trong tài liệu đặc tả được cài đặt tại file nào trong hệ thống logic:

### 1. Thư viện lõi biến đổi nhân tố: `playground/scoring/lib/transformer.py`

* **Tỷ Suất Sinh Lời Logarit ($R_t$)**
    * *Công thức*: $$R_{t}=\ln\left(\frac{P_{t}}{P_{t-1}}\right)$$ [cite: 299]
    * [cite_start]*Mục đích*: Trích xuất động lượng giá liên tục, đưa chuỗi giá phi trạm $I(1)$ về trạng thái trạm $I(0)$[cite: 300, 301].
    * *Vị trí hàm*: `calc_log_return(df, col)`

* **Chuẩn Hóa Rolling Z-Score ($Z_t$)**
    * *Công thức*: $$Z_{t}=\frac{X_{t}-\mu_{t}}{\sigma_{t}}$$ [cite: 305]
    * [cite_start]Trong đó $\mu_{t}$ và $\sigma_{t}$ là trung bình cuốn và độ lệch chuẩn cuốn trên cửa sổ trượt độ rộng $N$[cite: 306, 307].
    * [cite_start]*Mục đích*: Đưa các nhân tố bất đồng nhất về không gian biểu diễn thống kê đồng nhất không thứ nguyên (Dimensionless Z-Space)[cite: 308, 309].
    * *Vị trí hàm*: `calc_rolling_zscore(df, col, window)`

* **Hệ Số Góc Hồi Quy Tuyến Tính Trượt ($m_{OLS}$)**
    * [cite_start]*Công thức*: $$T_{t}=m=\frac{N\sum_{j=1}^{N}(x_{j}y_{j})-\sum_{j=1}^{N}x_{j}\sum_{j=1}^{N}y_{j}}{N\sum_{j=1}^{N}x_{j}^{2}-(\sum_{j=1}^{N}x_{j})^{2}}$$ [cite: 316]
    * *Mục đích*: Đo lường gia tốc xu hướng của hành động giá và giảm thiểu sai số pha (Phase Error)[cite: 322, 326].
    * *Vị trí hàm*: `calc_rolling_ols_slope(df, col, window)`

* **Hàm Phạt Biến Động Rủi Ro Hàm Mũ CARA ($R_t$)**
    * *Công thức*: $$R_{t}=e^{-\lambda Z_{vol,t}}$$ [cite: 371]
    * [cite_start]Bọc màng lọc an toàn giới hạn hệ số phạt: `.clip(upper_bound=1.0)` để $R_t \in (0, 1]$[cite: 376].
    * [cite_start]*Mục đích*: Áp dụng hàm phạt phi tuyến tính theo cấp số nhân đối với các tài sản có biến động tăng vọt nhằm phòng vệ danh mục[cite: 375, 377].
    * *Vị trí hàm*: `calc_cara_penalty(df, vol_col, lambda_risk)`

### 2. Thư viện trực giao hóa nhân tố: `playground/scoring/lib/ortho.py`

* **Trực Giao Hóa Không Gian Nhân Tố Bằng PCA**
    * [cite_start]*Công thức*: Thực hiện phân rã trị riêng ma trận hiệp phương sai cuốn $\Sigma_{t}v_{i}=\lambda_{i}v_{i}$ [cite: 334, 338][cite_start], sắp xếp $\lambda_{1}\ge\lambda_{2}\ge\lambda_{3}$[cite: 340]. Trích xuất thành phần chính đầu tiên: $$Z_{momentum\_ortho,t}=v_{1}^{T}X_{t}$$ [cite: 341, 343]
    * [cite_start]*Mục đích*: Loại bỏ hiện tượng đếm trùng (Double Counting) do sự cộng tuyến thông tin của các chỉ báo động lượng giá[cite: 330].
    * *Vị trí hàm*: `orthogonalize_momentum(df, cols)`

### 3. Thư viện tính toán điểm số: `playground/scoring/lib/score.py`

* **Điểm Sức Khỏe Cơ Sở ($H_t$)**
    * *Công thức*: $$H_{t}=w_{1}Z_{momentum\_ortho,t}+w_{2}Z_{sentiment,t}+w_{3}Z_{impact,t}$$ [cite: 383]
    * [cite_start]Ràng buộc chuẩn hóa L1-Norm: $\sum|w_{i}|=1$[cite: 384, 385].
    * *Vị trí hàm*: Cài đặt tích chập ma trận trong `calculate_dual_scores(df)`

* **Galaxy Alpha Score™**
    * *Công thức*: $$\text{GalaxyAlphaScore}_{t} = 100 \times \sigma(H_{t}) = \frac{100}{1+e^{-H_{t}}}$$ [cite: 392]
    * [cite_start]*Mục đích*: Nén không gian điểm Z-Score vô hạn về thang đo chuẩn giới hạn $[0, 100]$ để định vị cơ hội tăng trưởng[cite: 393, 394].
    * *Vị trí hàm*: Tích hợp hàm kích hoạt Sigmoid trong `calculate_dual_scores(df)`

* **Galaxy Safety Score™**
    * [cite_start]*Công thức*: $$\text{GalaxySafetyScore}_{t} = 100 \times \sigma(H_{t}) \times R_{t} = \frac{100}{1+e^{-H_{t}}} \times e^{-\lambda Z_{vol,t}}$$ [cite: 399]
    * [cite_start]*Mục đích*: Tích hợp trực tiếp hàm phạt rủi ro CARA vào điểm cơ sở làm bộ lọc biên phòng vệ hệ thống[cite: 397, 398, 400].
    * *Vị trí hàm*: Kết hợp nhân tử rủi ro trong `calculate_dual_scores(df)`

### 4. Thư viện luật phân kỳ hình học: `playground/scoring/lib/rules.py`

* **Bộ Xác Thực Trễ Hình Học Fractal (Fractal Confirmation Delay)**
    * *Công thức Swing High tại mốc $T-\omega$*: 
        $$\text{Swing\_High\_Confirmed}(P_{T-\omega}) = \begin{cases} 1 & \text{nếu } P_{T-\omega} > P_{T-\omega-k} \wedge P_{T-\omega} > P_{T-\omega+k} \;\; \forall k \in [1,\omega] \\ 0 & \text{trong các trường hợp khác} \end{cases}$$
    * *Công thức Swing Low tại mốc $T-\omega$*: 
        $$\text{Swing\_Low\_Confirmed}(P_{T-\omega}) = \begin{cases} 1 & \text{nếu } P_{T-\omega} < P_{T-\omega-k} \wedge P_{T-\omega} < P_{T-\omega+k} \;\; \forall k \in [1,\omega] \\ 0 & \text{trong các trường hợp khác} \end{cases}$$
    * *Mục đích*: Khắc phục sai số nhìn trước tương lai (Look-Ahead Bias) bằng cách lùi cửa sổ xác nhận hình học một khoảng cố định bằng chu kỳ $\omega$.
    * *Vị trí hàm*: `calc_fractal_swings(df, col, omega)`

* **Khoảng Cách Kullback-Leibler ($D_{KL}$)**
    * *Công thức*: 
        $$D_{KL}(P||S)=\sum_{x\in\mathcal{X}}P(x)\log\left(\frac{P(x)}{S(x)}\right)$$
    * *Mục đích*: Đo lường Relative Entropy giữa phân phối giá ($P$) và tâm lý xã hội ($S$) đóng vai trò làm Bộ hiệu chỉnh hệ số tự tin (Confidence Modifier) nhằm xóa bỏ tín hiệu phân kỳ giả.
    * *Vị trí hàm*: `calc_kl_divergence(df, window)`

* **Khoảng Cách Kullback-Leibler ($D_{KL}$)**
    * *Công thức*: $$D_{KL}(P||S)=\sum_{x\in\mathcal{X}}P(x)\log\left(\frac{P(x)}{S(x)}\right)$$ [cite: 434]
    * [cite_start]*Mục đích*: Đo lường Relative Entropy giữa phân phối giá ($P$) và tâm lý xã hội ($S$) đóng vai trò làm Bộ hiệu chỉnh hệ số tự tin (Confidence Modifier) nhằm xóa bỏ tín hiệu phân kỳ giả[cite: 435, 436, 437].
    * *Vị trí hàm*: `calc_kl_divergence(df, window)`

---

## Nhạc Trưởng Điều Phối (Execution Orchestrators)

Hệ thống cung cấp hai luồng thực thi độc lập tương ứng với môi trường vận hành:

### A. Môi trường Giả lập & Đối soát: `playground/scoring/test/run.py`
[cite_start]Luồng xử lý chạy Batch trích xuất dữ liệu mẫu từ nguồn dữ liệu giả lập hệ thống `lib/mock_data_v2.py`[cite: 443]. Hỗ trợ các tham số CLI kiểm thử nhanh trạng thái phản ứng của thuật toán:
```bash
# 1. Kiểm thử Phân kỳ dương (Gom hàng bắt đáy)
uv run python test/run.py --case bullish_divergence

# 2. Kiểm thử Phân kỳ âm (Bẫy giá tăng - FOMO đỉnh)
uv run python test/run.py --case bearish_divergence

# 3. Kiểm thử Biến động hoảng loạn (Dao rơi tự do - Kích hoạt CARA cực đại)
uv run python test/run.py --case high_volatility_panic