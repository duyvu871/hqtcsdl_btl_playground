# Báo cáo thiết kế Step 5 — Influence Weighting

## 1. Giới thiệu chung

Trong pipeline phân tích dữ liệu mạng xã hội và tin tức cho thị trường tiền mã hóa, **Step 5 — Influence Weighting** được xây dựng với mục tiêu đánh giá mức độ ảnh hưởng của từng sự kiện thông tin sau khi sự kiện đó đã được phân tích cảm xúc ở Step 4. Nếu Step 4 cho biết một bài viết hoặc một tin tức đang mang sắc thái tích cực, tiêu cực hay trung lập đối với một đồng coin, thì Step 5 trả lời câu hỏi quan trọng hơn: **tín hiệu cảm xúc đó nên được tính nặng bao nhiêu khi đưa sang bước scoring cuối cùng?**

Trong thực tế, không phải mọi bài viết trên mạng xã hội đều có giá trị như nhau. Một bài đăng tích cực về Bitcoin từ một tài khoản nhỏ, ít tương tác không nên có sức nặng tương đương với một bài đăng tích cực từ một tài khoản lớn, có nhiều lượt chia sẻ và tạo ra thảo luận mạnh. Tương tự, một tin tức từ nguồn uy tín có thể đáng tin cậy hơn một bài viết mang tính quảng bá, spam hoặc được đăng lặp lại bởi nhiều tài khoản. Vì vậy, Step 5 đóng vai trò như một lớp điều chỉnh trọng số, giúp hệ thống chuyển từ **sentiment thô** sang **sentiment đã được điều chỉnh theo mức độ ảnh hưởng**.

Luồng dữ liệu của Step 5 được thiết kế như sau:

```text
sentiment_events        # Output của Step 4 — Sentiment Analysis
        ↓
weighted_events         # Mỗi event được gắn influence_weight
        ↓
influence_aggregates    # Dữ liệu tổng hợp theo coin và thời gian cho Step 6
```
---

## 2. Vai trò của Influence Weighting trong pipeline

Sau Step 4, mỗi event thường đã có các thông tin như `coin_id`, `sentiment_score`, `sentiment_label` và `sentiment_confidence`. Nếu hệ thống đưa trực tiếp các điểm sentiment này vào Step 6, hệ thống sẽ mặc định rằng mọi event có cùng tầm quan trọng. Cách tiếp cận này có thể gây sai lệch vì thị trường crypto chịu ảnh hưởng mạnh bởi tính lan truyền của thông tin, độ uy tín của nguồn phát và tốc độ phản ứng của cộng đồng.

Ví dụ, hai event cùng có `sentiment_score = 0.8` đối với BTC:

```text
Event A: tài khoản nhỏ, 3 likes, không có retweet.
Event B: tài khoản lớn, nhiều follower, 20,000 likes và 5,000 retweets.
```

Cả hai event đều mang sắc thái tích cực, nhưng tác động tiềm năng đến thị trường không giống nhau. Event B có khả năng lan truyền rộng hơn và có thể ảnh hưởng đến nhận thức của nhiều nhà đầu tư hơn. Vì vậy, Step 5 tạo ra chỉ số `influence_weight` để điều chỉnh mức độ đóng góp của mỗi event.

Kết quả quan trọng nhất của Step 5 là:

```text
weighted_sentiment = sentiment_score × influence_weight
```

Trong đó, `weighted_sentiment` là tín hiệu cảm xúc đã được điều chỉnh theo mức độ ảnh hưởng. Đây là dữ liệu có giá trị hơn để Step 6 sử dụng khi tổng hợp tín hiệu và tạo trading signal.

---

## 3. Cơ sở lý thuyết

### 3.1. Popularity không đồng nghĩa với influence

Một hiểu nhầm phổ biến khi đo lường ảnh hưởng trên mạng xã hội là cho rằng tài khoản có nhiều người theo dõi sẽ luôn có ảnh hưởng lớn. Trên thực tế, **popularity** và **influence** là hai khái niệm khác nhau. Popularity phản ánh mức độ được chú ý, trong khi influence phản ánh khả năng làm thay đổi nhận thức, hành vi hoặc mức độ lan truyền thông tin trong cộng đồng.

Một tài khoản có nhiều follower nhưng ít tương tác thực tế có thể không tạo ra ảnh hưởng lớn. Ngược lại, một tài khoản nhỏ nhưng có bài viết được chia sẻ mạnh, tạo ra nhiều phản hồi và được cộng đồng thảo luận rộng rãi có thể tạo ra ảnh hưởng đáng kể. Vì vậy, Step 5 không sử dụng trực tiếp số lượng follower làm influence score, mà kết hợp follower với engagement, độ mới của thông tin, độ tin cậy của nguồn và mức độ viral bất thường.

### 3.2. Engagement phản ánh khả năng lan truyền thông tin

Engagement là nhóm chỉ số thể hiện mức độ người dùng phản ứng với một nội dung. Các chỉ số như like, reply, comment, quote, retweet, share, bookmark hoặc impression đều phản ánh một phần khả năng lan truyền của event. Tuy nhiên, các loại engagement không có cùng ý nghĩa.

Một lượt like chỉ thể hiện phản ứng nhẹ. Một reply hoặc comment cho thấy nội dung tạo ra thảo luận. Một retweet, repost hoặc share thể hiện việc người dùng chủ động lan truyền nội dung đến mạng lưới của họ. Vì vậy, trong công thức của Step 5, các loại engagement được gán trọng số khác nhau.

Cách tính `raw_engagement` được đề xuất như sau:

```text
raw_engagement =
    1.0 × likes
  + 2.0 × replies/comments
  + 3.0 × quotes
  + 4.0 × retweets/shares
  + 1.5 × bookmarks
  + 0.001 × impressions/views
  + 1.0 × reddit_score
```

Việc gán trọng số cao hơn cho retweet/share là hợp lý vì đây là hành động làm nội dung được phát tán sang nhiều người dùng khác, từ đó làm tăng khả năng tác động đến tâm lý thị trường.

### 3.3. Weighted sentiment phù hợp hơn sentiment thô

Trong bài toán dự đoán tín hiệu thị trường từ dữ liệu social/news, sentiment thô chỉ cho biết nội dung tích cực hay tiêu cực, nhưng chưa phản ánh mức độ quan trọng của nguồn thông tin. Nếu chỉ lấy trung bình sentiment, một lượng lớn bài viết chất lượng thấp có thể làm nhiễu tín hiệu, trong khi những bài viết có ảnh hưởng cao lại không được phản ánh đúng mức.

Do đó, Step 5 sử dụng nguyên tắc **weighted sentiment**. Theo nguyên tắc này, sentiment của mỗi event được nhân với trọng số ảnh hưởng của chính event đó. Cách tiếp cận này giúp hệ thống ưu tiên các tín hiệu đến từ nguồn uy tín, có tương tác cao, còn mới và ít dấu hiệu nhiễu.

### 3.4. Tính thời gian rất quan trọng trong thị trường crypto

Thị trường crypto phản ứng nhanh với tin tức và thông tin trên mạng xã hội. Một bài viết mới trong vài phút hoặc vài giờ gần đây thường có giá trị tín hiệu cao hơn một bài viết đã cũ nhiều ngày. Vì vậy, Step 5 cần có cơ chế giảm trọng số theo thời gian, gọi là `TimeDecay`.

Cơ chế này đảm bảo rằng những event cũ không biến mất hoàn toàn, nhưng ảnh hưởng của chúng giảm dần theo thời gian. Điều này giúp Step 6 ưu tiên các tín hiệu còn mới và có khả năng phản ánh trạng thái hiện tại của thị trường.

---

## 4. Input của Step 5

Input chính của Step 5 là collection `sentiment_events`, tức output của Step 4. Mỗi document trong collection này đại diện cho một event đã được nhận diện coin và phân tích sentiment.

Một input event có thể có cấu trúc như sau:

```json
{
  "sentiment_id": "sent_001",
  "mapped_id": "map_001",
  "event_id": "evt_001",
  "coin_id": "BTC",
  "source": "twitter",
  "author_id": "user_123",
  "clean_text": "Bitcoin is gaining momentum after ETF inflows...",
  "timestamp": 1716113000,
  "metrics": {
    "followers": 50000,
    "likes": 1200,
    "retweets": 150,
    "replies": 80,
    "quotes": 30,
    "impressions": 200000
  },
  "sentiment_score": 0.82,
  "sentiment_label": "positive",
  "sentiment_confidence": 0.93,
  "ner": {
    "confidence": 1.0
  },
  "filter": {
    "spam_probability": 0.05,
    "duplicate_penalty": 1.0
  }
}
```

Trong trường hợp một số field không tồn tại, module Influence Weighting vẫn sử dụng giá trị mặc định an toàn. Ví dụ, nếu không có `ner.confidence`, hệ thống mặc định là `1.0`; nếu không có `spam_probability`, hệ thống mặc định là `0.0`. Cách xử lý này giúp Step 5 không bị lỗi khi output của Step 4 chưa truyền đủ metadata.

---

## 5. Các yếu tố hình thành Influence Weight

Influence Weight được thiết kế từ nhiều nhóm yếu tố thay vì chỉ dựa vào một chỉ số duy nhất. Các yếu tố chính bao gồm: `SourceWeight`, `TimeDecay`, `QualityScore`, `AuthorAuthority`, `EngagementStrength`, `ViralitySurprise` và `NetworkInfluence`.

### 5.1. SourceWeight — trọng số theo nguồn dữ liệu

Không phải mọi nguồn dữ liệu đều có độ tin cậy và ý nghĩa giống nhau. Một bài news từ nguồn uy tín thường có tính xác thực cao hơn một bài đăng ngắn trên social media. Ngược lại, social media lại có ưu điểm là phản ánh phản ứng cộng đồng rất nhanh.

Vì vậy, Step 5 sử dụng `SourceWeight` để điều chỉnh độ quan trọng ban đầu theo nguồn dữ liệu:

```text
Twitter/X  → 1.00
Reddit     → 0.90
News       → 1.20
Default    → 1.00
```

Các giá trị này không có nghĩa news luôn tốt hơn social media, mà phản ánh giả định rằng news có độ tin cậy cao hơn, còn Twitter/X và Reddit có tính phản ứng cộng đồng mạnh hơn. Trong tương lai, các giá trị này có thể được hiệu chỉnh bằng dữ liệu thực nghiệm.

### 5.2. TimeDecay — trọng số theo độ mới của event

`TimeDecay` làm giảm ảnh hưởng của event khi event cũ dần. Công thức được sử dụng là exponential decay với half-life:

```text
TimeDecay = exp(-ln(2) × age_hours / half_life_hours)
```

Trong đó:

```text
age_hours        = số giờ tính từ lúc event được tạo đến hiện tại
half_life_hours  = số giờ để ảnh hưởng giảm còn một nửa
```

Half-life có thể khác nhau theo nguồn:

```text
Twitter/X  → 12 giờ
Reddit     → 24 giờ
News       → 36 giờ
```

Cách thiết kế này phản ánh đặc điểm rằng Twitter/X có tốc độ lan truyền nhanh nhưng cũng nhanh lỗi thời, trong khi news thường có vòng đời thông tin dài hơn.

### 5.3. QualityScore — chất lượng và độ tin cậy của event

`QualityScore` được dùng để giảm ảnh hưởng của các event có dấu hiệu không đáng tin cậy. Thành phần này tận dụng kết quả của các bước trước như filter, NER và sentiment confidence.

Công thức khái quát:

```text
QualityScore =
    ner_confidence
  × sentiment_confidence
  × (1 - spam_probability)
  × duplicate_penalty
```

Ý nghĩa của từng thành phần:

```text
ner_confidence         → độ chắc chắn rằng event thực sự nói về coin đó
sentiment_confidence   → độ chắc chắn của kết quả sentiment
spam_probability       → xác suất event là spam hoặc nội dung chất lượng thấp
duplicate_penalty      → hệ số phạt nếu nội dung bị trùng lặp hoặc gần trùng lặp
```

Nếu một event có sentiment tích cực nhưng bị nghi ngờ là spam hoặc có độ chắc chắn thấp, event đó không nên đóng góp quá mạnh vào kết quả cuối cùng. Vì vậy, `QualityScore` đóng vai trò như một lớp kiểm soát chất lượng dữ liệu.

### 5.4. AuthorAuthority — độ uy tín của tác giả

`AuthorAuthority` phản ánh mức độ đáng chú ý và đáng tin cậy của tác giả. Thành phần này không chỉ dựa trên số follower, vì follower có thể bị thổi phồng hoặc không phản ánh tương tác thực tế. Thay vào đó, hệ thống kết hợp nhiều yếu tố:

```text
followers
average_author_engagement
verified status
account age
```

Cách tiếp cận tổng quát:

```text
AuthorAuthority =
    0.50 × follower_score
  + 0.35 × avg_author_engagement_score
  + 0.15 × verified_score
```

Trong đó follower và engagement được biến đổi bằng log/sigmoid để tránh việc tài khoản cực lớn làm lệch toàn bộ kết quả. Nếu dữ liệu về tuổi tài khoản hoặc verified status chưa có, module sẽ bỏ qua hoặc gán giá trị mặc định.

### 5.5. EngagementStrength — mức độ tương tác của event

`EngagementStrength` đo mức độ phản ứng thực tế mà event nhận được. Thành phần này dựa trên `raw_engagement`, sau đó được biến đổi log và chuẩn hóa để giảm ảnh hưởng của các giá trị ngoại lai.

Ý tưởng chính là một event có nhiều retweet, reply và quote thường có sức lan truyền mạnh hơn event chỉ có vài lượt like. Tuy nhiên, nếu dùng trực tiếp số engagement, các bài viral cực lớn có thể áp đảo toàn bộ hệ thống. Vì vậy, module sử dụng biến đổi log và sigmoid để đưa điểm về khoảng ổn định.

Cách tiếp cận này giúp hệ thống phân biệt được event có tương tác thấp, trung bình và cao, đồng thời hạn chế tình trạng một event duy nhất chi phối toàn bộ kết quả.

### 5.6. ViralitySurprise — mức viral bất thường

`ViralitySurprise` là thành phần nâng cao nhằm phát hiện những event có mức tương tác cao bất thường so với mức bình thường của chính tác giả hoặc của nguồn dữ liệu.

Ví dụ, một tài khoản lớn nhận 100,000 likes có thể là điều bình thường. Nhưng một tài khoản nhỏ thường chỉ có 50 likes mà đột nhiên nhận 5,000 likes thì đó là tín hiệu rất đáng chú ý. Trường hợp thứ hai có thể cho thấy thông tin đang lan truyền bất thường trong cộng đồng.

Công thức khái quát:

```text
ViralitySurprise = log(1 + current_engagement / expected_engagement)
```

Trong đó:

```text
current_engagement   = engagement hiện tại của event
expected_engagement  = engagement kỳ vọng của tác giả hoặc nguồn dữ liệu
```

Nếu chưa có dữ liệu lịch sử của tác giả, hệ thống có thể dùng median engagement của nguồn hoặc một giá trị mặc định.

### 5.7. NetworkInfluence — ảnh hưởng mạng lưới

`NetworkInfluence` là thành phần mở rộng, dùng khi hệ thống có dữ liệu về quan hệ giữa các user như reply, quote, retweet hoặc mention. Khi có đủ dữ liệu, có thể xây dựng graph:

```text
Node  = user/author
Edge  = quan hệ retweet, reply, quote hoặc mention
Weight = số lần tương tác
```

Sau đó, các thuật toán như PageRank hoặc centrality có thể được sử dụng để đo vị trí ảnh hưởng của tác giả trong mạng lưới. Trong phiên bản hiện tại, thành phần này được để sẵn với giá trị mặc định là `0.0`, vì các bước trước chưa đảm bảo cung cấp đầy đủ dữ liệu graph.

---

## 6. Công thức Influence Weight

Công thức tổng quát của Step 5 được thiết kế như sau:

```text
InfluenceWeight = clip(
    SourceWeight × TimeDecay × QualityScore ×
    (1 + CoreScale × (
        α × AuthorAuthority
      + β × EngagementStrength
      + γ × ViralitySurprise
      + δ × NetworkInfluence
    )),
    0,
    MaxInfluence
)
```

Các hệ số mặc định:

```text
α = 0.35
β = 0.40
γ = 0.25
δ = 0.00
CoreScale = 8.0
MaxInfluence = 20.0
```

Trong công thức này, `AuthorAuthority`, `EngagementStrength`, `ViralitySurprise` và `NetworkInfluence` tạo thành phần lõi của điểm ảnh hưởng. `SourceWeight`, `TimeDecay` và `QualityScore` đóng vai trò điều chỉnh theo bối cảnh nguồn dữ liệu, độ mới và chất lượng event.

Việc sử dụng `clip` là cần thiết để giới hạn điểm ảnh hưởng trong một khoảng hợp lý. Nếu không giới hạn, một vài event có lượng tương tác quá lớn có thể chi phối toàn bộ kết quả aggregate, làm Step 6 tạo ra tín hiệu thiên lệch.

---

## 7. Output 1 — weighted_events

Output đầu tiên của Step 5 là collection `weighted_events`. Collection này lưu từng event sau khi đã được tính influence weight.

Ví dụ:

```json
{
  "weighted_id": "weighted_001",
  "sentiment_id": "sent_001",
  "mapped_id": "map_001",
  "event_id": "evt_001",
  "coin_id": "BTC",
  "source": "twitter",
  "author_id": "user_123",
  "timestamp": 1716113000,
  "sentiment_score": 0.82,
  "sentiment_label": "positive",
  "sentiment_confidence": 0.93,
  "influence_weight": 5.98,
  "weighted_sentiment": 4.9036,
  "influence": {
    "source_weight": 1.0,
    "time_decay": 0.93,
    "quality_score": 0.91,
    "author_authority": 0.72,
    "engagement_strength": 0.88,
    "virality_surprise": 0.61,
    "network_influence": 0.0,
    "raw_engagement": 3820.0,
    "influence_weight": 5.98
  },
  "weighted_at": 1716115000
}
```

Collection này có ý nghĩa lưu vết chi tiết, giúp kiểm tra vì sao một event được tính nặng hoặc nhẹ. Khi cần debug, người dùng có thể xem từng thành phần trong object `influence`.

---

## 8. Output 2 — influence_aggregates

Output thứ hai của Step 5 là collection `influence_aggregates`. Đây là dữ liệu đã được tổng hợp theo `coin_id` và khung thời gian, dùng làm input trực tiếp cho Step 6.

Step 6 thường không cần đọc từng bài viết riêng lẻ. Thay vào đó, Step 6 cần các chỉ số tổng hợp như social volume, average sentiment, weighted sentiment và tổng influence trong mỗi window thời gian.

Ví dụ output:

```json
{
  "coin_id": "BTC",
  "timeframe": "1h",
  "timestamp": "2026-06-13T09:00:00Z",
  "window_start": "2026-06-13T09:00:00Z",
  "window_end": "2026-06-13T10:00:00Z",
  "event_count": 245,
  "social_volume": 245,
  "avg_sentiment": 0.31,
  "sentiment_score": 0.47,
  "influence_weighted_sentiment": 0.47,
  "total_weighted_sentiment": 386.12,
  "total_influence": 821.55,
  "avg_influence": 3.35,
  "max_influence": 16.20
}
```

Trong đó:

```text
influence_weighted_sentiment = total_weighted_sentiment / total_influence
sentiment_score              = alias của influence_weighted_sentiment
social_volume                = số lượng event trong window
```

Field `sentiment_score` được giữ lại để Step 6 có thể đọc trực tiếp như một social sentiment signal đã được chuẩn hóa.

---

## 9. Cách aggregate weighted sentiment

Sau khi tính `weighted_sentiment` cho từng event, Step 5 tổng hợp dữ liệu theo từng coin và từng window thời gian. Công thức aggregate quan trọng nhất là:

```text
InfluenceWeightedSentiment =
    sum(sentiment_score × influence_weight)
    /
    sum(influence_weight)
```

Công thức này đảm bảo rằng các event có influence cao sẽ tác động mạnh hơn đến sentiment tổng hợp, nhưng vẫn được chuẩn hóa bởi tổng influence để kết quả không bị phóng đại theo số lượng event.

Ví dụ:

```text
Event A: sentiment = 0.8, influence = 2
Event B: sentiment = -0.4, influence = 10
```

Khi đó:

```text
weighted sentiment = (0.8 × 2 + -0.4 × 10) / (2 + 10)
                   = (1.6 - 4.0) / 12
                   = -0.2
```

Mặc dù có một event tích cực, tín hiệu tổng hợp vẫn nghiêng về tiêu cực vì event tiêu cực có ảnh hưởng lớn hơn.

---

## 10. Vì sao Step 5 không nên đọc raw_events

Step 5 không nên lấy dữ liệu trực tiếp từ `raw_events`, vì raw event chưa có đủ thông tin cần thiết để tính influence một cách đúng nghĩa. Một raw event có thể có text, author và metrics, nhưng thường chưa biết chắc:

```text
bài viết nói về coin nào
coin mapping có đáng tin cậy không
sentiment là tích cực hay tiêu cực
sentiment confidence là bao nhiêu
event có bị nghi spam hoặc duplicate không
```

Nếu Step 5 đọc trực tiếp từ raw event, module chỉ có thể tính một dạng điểm ảnh hưởng của tác giả, nhưng chưa thể tạo ra `weighted_sentiment`. Vì vậy, input hợp lý của Step 5 là `sentiment_events`, tức dữ liệu đã đi qua filter, NER và sentiment.

---

## 11. Cấu trúc module

Module được tổ chức trong folder:

```text
playground/influence/
├── README.md
├── .env.example
├── pyproject.toml
├── run.py
├── main.py
├── lib/
│   ├── config.py
│   ├── scoring.py
│   ├── schema.py
│   ├── mongo.py
│   ├── aggregate.py
│   └── progress.py
└── tests/
    └── test_scoring.py
```

Ý nghĩa các file chính:

```text
run.py        → CLI chính để chạy Step 5
main.py       → wrapper gọi run.py
scoring.py    → công thức tính influence weight
schema.py     → chuẩn hóa input/output document
mongo.py      → đọc sentiment_events và ghi weighted_events
aggregate.py  → tổng hợp weighted_events thành influence_aggregates
config.py     → đọc cấu hình từ biến môi trường
progress.py   → hiển thị tiến trình xử lý
tests/        → kiểm thử công thức scoring
```

---

## 12. Cấu hình và cách chạy

Các biến môi trường quan trọng:

```env
MONGODB_URI=mongodb://localhost:27017
MONGODB_DB=crypto_prediction
MONGODB_SENTIMENT_COLLECTION=sentiment_events
MONGODB_WEIGHTED_COLLECTION=weighted_events
MONGODB_INFLUENCE_AGG_COLLECTION=influence_aggregates

MAX_INFLUENCE=20
CORE_SCALE=8
ALPHA_AUTHOR=0.35
BETA_ENGAGEMENT=0.40
GAMMA_VIRALITY=0.25
DELTA_NETWORK=0.0
```

Chạy thử không ghi database:

```bash
uv run python run.py --dry-run -v --limit 20
```

Ghi `weighted_events`:

```bash
uv run python run.py --limit 500
```

Ghi `weighted_events` và aggregate sang `influence_aggregates`:

```bash
uv run python run.py --limit 500 --aggregate --timeframe 1h
```

Chỉ aggregate lại từ dữ liệu đã có:

```bash
uv run python run.py --aggregate-only --timeframe 1h
```

---

## 13. Index MongoDB đề xuất

Để tăng tốc truy vấn và tránh xử lý trùng event, module tạo hoặc khuyến nghị các index sau:

```text
weighted_events:
- unique index: sentiment_id + coin_id
- index: coin_id
- index: timestamp
- index: source

influence_aggregates:
- unique index: coin_id + timeframe + window_start
- index: timestamp
- index: timeframe
```

Các index này giúp Step 5 có thể xử lý lại dữ liệu mà không tạo bản ghi trùng, đồng thời giúp Step 6 truy vấn nhanh dữ liệu aggregate theo coin và timeframe.

---

## 14. Hạn chế hiện tại và hướng mở rộng

Phiên bản hiện tại của Step 5 đã có thể tính influence ở cấp event và aggregate dữ liệu cho Step 6. Tuy nhiên, vẫn còn một số giới hạn.

Thứ nhất, `NetworkInfluence` hiện mới được để sẵn trong công thức, nhưng chưa thể tính đầy đủ nếu pipeline chưa lưu dữ liệu quan hệ giữa các user. Để triển khai thành phần này, hệ thống cần thu thập thêm thông tin về retweet, reply, quote hoặc mention giữa các tài khoản.

Thứ hai, `ViralitySurprise` sẽ chính xác hơn nếu có dữ liệu lịch sử dài hạn của từng author. Trong trường hợp chưa có dữ liệu lịch sử, module phải dùng giá trị mặc định hoặc median theo source, khiến độ chính xác chưa tối ưu.

Thứ ba, các hệ số như `ALPHA_AUTHOR`, `BETA_ENGAGEMENT`, `GAMMA_VIRALITY` và `MAX_INFLUENCE` hiện được đặt theo thiết kế thủ công. Trong tương lai, các hệ số này có thể được hiệu chỉnh bằng backtesting hoặc học máy dựa trên dữ liệu giá thực tế.

---

## 15. Kết luận

Step 5 — Influence Weighting là bước trung gian quan trọng giữa Sentiment Analysis và Scoring. Nếu Step 4 chỉ cho biết thị trường đang được nói đến theo hướng tích cực hay tiêu cực, thì Step 5 đánh giá mức độ đáng tin cậy và mức độ lan truyền của các tín hiệu đó.

Bằng cách kết hợp source weight, time decay, quality score, author authority, engagement strength, virality surprise và network influence, module tạo ra `influence_weight` cho từng event. Từ đó, hệ thống tính được `weighted_sentiment` và tổng hợp thành `influence_aggregates` cho Step 6.

Cách thiết kế này giúp pipeline tránh việc coi mọi bài viết có giá trị như nhau, giảm tác động của spam/noise, ưu tiên thông tin mới và có khả năng lan truyền cao, đồng thời tạo ra dữ liệu social signal có chất lượng hơn cho bước scoring cuối cùng.

---

## 16. Tài liệu tham khảo

- Cha, M., Haddadi, H., Benevenuto, F., & Gummadi, K. P. (2010). *Measuring User Influence in Twitter: The Million Follower Fallacy*.
- Romero, D. M., Galuba, W., Asur, S., & Huberman, B. A. (2011). *Influence and Passivity in Social Media*.
- Pagolu, V. S., Reddy, K. N., Panda, G., & Majhi, B. (2016). *Sentiment Analysis of Twitter Data for Predicting Stock Market Movements*.
- Abraham, J., Higdon, D., Nelson, J., & Ibarra, J. (2018). *Cryptocurrency Price Prediction Using Tweet Volumes and Sentiment Analysis*.
- X API Documentation. *Public metrics and data dictionary*.
- Reddit data documentation. *Score, comments and upvote ratio*.
- LunarCrush documentation and glossary. *Social metrics, sentiment and influence-based crypto analytics*.
