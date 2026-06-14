# Cơ sở lý thuyết Pipeline — theo Stage

Tài liệu lý thuyết chi tiết cho từng bước pipeline, trình bày theo **khung 5 mục** trong [`../pipeline-theory-form.md`](../pipeline-theory-form.md):

1. Tổng quan (Khái niệm · Vai trò)  
2. Kiến trúc và thành phần cốt lõi  
3. Cơ chế hoạt động và vai trò trong Pipeline  
4. Ưu điểm và Hạn chế  
5. Lý do lựa chọn  

| Stage | Công nghệ | Tài liệu | DOCX |
| --- | --- | --- | --- |
| 1 | Data Ingestion | [`ingest.md`](ingest.md) | [`ingest.docx`](ingest.docx) |
| 2 | Spam / Noise Filter | [`spam-filter.md`](spam-filter.md) | [`spam-filter.docx`](spam-filter.docx) |
| 3 | NER / Coin Mapping | [`ner-mapping.md`](ner-mapping.md) | [`ner-mapping.docx`](ner-mapping.docx) |
| 4 | Sentiment | *(chưa có)* | — |
| 5 | Influence | *(chưa có)* | — |
| 6 | Scoring | *(chưa có)* | — |

**Export DOCX:** `pandoc <file>.md -o <file>.docx --standalone --resource-path=. --toc`

**Tham chiếu:** [`pipeline-overview.md`](../pipeline-overview.md) · [`khung-bao-cao.md`](../khung-bao-cao.md)
