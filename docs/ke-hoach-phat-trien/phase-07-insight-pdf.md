# P7 — Stage 7: LLM Insight + PDF

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §5.4 event_type `llm_token` / `report_done`  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.3 Payload mẫu analysis/latest · §3.3.5 PDF export

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P6 — Orchestrator](phase-06-orchestrator.md) |
| **FR liên quan** | **FR-08** (LLM Insight stream report) · **FR-09** (PDF export báo cáo) |
| **Điều hướng** | [← P6](phase-06-orchestrator.md) · [P8 →](phase-08-api-websocket.md) |

---

## 1. Mục tiêu

- **Stage 7 (Insight):** Gọi OpenRouter LLM, stream từng `llm_token` vào control bus, ghi `analysis_reports` + `chat_messages` (type=report) khi xong, emit `report_done`.
- **PDF Export:** Từ session data (session header + ETL summary + signal card + LLM report markdown) → PDF file qua WeasyPrint.

---

## 2. Công việc & tái sử dụng

### 2.1. Stage 7 — Insight (`src/pipeline/insight/`)

```text
src/pipeline/insight/
├── __init__.py
├── worker.py       # dùng harness; stream llm_token; ghi report; emit report_done
├── prompt.py       # load + render config/prompts/insight_v1.txt
└── llm.py          # OpenRouter streaming API call
```

**`worker.py` insight** — luồng xử lý:
1. Nhận `scoring_signals` document từ `stage:insight:in`
2. Query context bổ sung từ MongoDB (top N `sentiment_events`, `influence_aggregates` của session)
3. Render prompt từ `config/prompts/insight_v1.txt` + context
4. Gọi OpenRouter streaming → nhận token từng cái
5. Mỗi token: emit `llm_token` vào `session:{id}:events`
6. Khi stream xong: ghi `analysis_reports` + `chat_messages` (type=report)
7. Emit `report_done`

**`prompt.py` — Prompt template `config/prompts/insight_v1.txt`:**
```
Bạn là chuyên gia phân tích crypto. Dựa trên dữ liệu sau:
- Coin: {coin_id}, Timeframe: {timeframe}
- Galaxy Alpha Score: {alpha}, Galaxy Safety Score: {safety}
- Action: {action} (confidence: {confidence}%)
- Social volume: {social_volume} posts, Weighted sentiment: {weighted_sentiment}
- Top events (tóm tắt):
{top_events}

Viết báo cáo gồm:
1. Tóm tắt tín hiệu (1 đoạn)
2. Key findings (3-5 điểm)
3. Risk factors (2-3 điểm)
4. Recommendation (1 đoạn ngắn)
5. Disclaimer: Không phải lời khuyên đầu tư.
```

**`llm.py` — OpenRouter streaming:**
```python
async def stream_insight(prompt: str, session_id: str):
    """Yield token strings; emit vào control bus."""
    async with openai.AsyncOpenAI(
        base_url="https://openrouter.ai/api/v1",
        api_key=settings.OPENROUTER_API_KEY,
    ).chat.completions.stream(
        model=settings.OPENROUTER_INSIGHT_MODEL,
        messages=[{"role": "user", "content": prompt}],
        stream=True,
    ) as stream:
        async for chunk in stream:
            token = chunk.choices[0].delta.content or ""
            if token:
                await emit(redis, session_id, "llm_token", {"token": token})
                yield token
```

**Fallback khi LLM lỗi:**
```python
# worker.py
try:
    full_text = ""
    async for token in stream_insight(prompt, session_id):
        full_text += token
    llm_fallback = False
except Exception as e:
    full_text = f"[LLM unavailable: {e}] Signal: {action} | Alpha: {alpha} | Safety: {safety}"
    llm_fallback = True
```

**Schema `analysis_reports` (§3.3.3):**
```json
{
  "report_id": "uuid",
  "session_id": "...",
  "coin_id": "BTC",
  "timeframe": "1h",
  "signal_id": "...",
  "summary": "BTC cho tín hiệu BUY với alpha 68.2...",
  "key_findings": ["Social volume tăng 23%...", "..."],
  "risk_factors": ["Volatility cao (ATR +18%)..."],
  "recommendation": "...",
  "confidence": 72.5,
  "full_text": "...markdown...",
  "llm_model": "anthropic/claude-3.5-sonnet",
  "llm_fallback": false,
  "generated_at": "2026-06-13T10:30:00Z"
}
```

**`chat_messages` type=report:**
```json
{
  "message_id": "...",
  "session_id": "...",
  "role": "assistant",
  "type": "report",
  "content": "...full markdown report...",
  "metadata": {"report_id": "...", "signal_id": "..."},
  "created_at": "..."
}
```

### 2.2. PDF Export (`src/api/services/pdf_export.py`)

**Nội dung PDF:**
1. Header: tên session, coin, timeframe, ngày tạo
2. Bảng ETL summary: stage | status | records_in | records_out | duration_ms (từ `pipeline_stage_runs`)
3. Signal card: action (BUY/HOLD) | Alpha | Safety | target_price | stop_loss
4. LLM report markdown → HTML → PDF

**WeasyPrint:**
```python
from weasyprint import HTML

async def generate_pdf(session_id: str) -> bytes:
    session  = await db.analysis_sessions.find_one({"session_id": session_id})
    report   = await db.analysis_reports.find_one({"session_id": session_id})
    stages   = await db.pipeline_stage_runs.find({"job_id": session["job_id"]}).to_list(20)
    signal   = await db.scoring_signals.find_one({"signal_id": report["signal_id"]})

    html_content = render_pdf_template(session, report, stages, signal)
    return HTML(string=html_content).write_pdf()
```

---

## 3. Kiểm thử

| Test ID | Mô tả | Input | Kết quả mong đợi |
|---------|-------|-------|------------------|
| T7-01 | LLM token stream thứ tự | Mock streaming response | Control stream nhận `llm_token` events theo đúng thứ tự |
| T7-02 | `analysis_reports` đủ field | Chạy Stage 7 | Tất cả field required trong schema có giá trị |
| T7-03 | `report_done` emit | Sau stream xong | Control stream có `event_type=report_done` với `report_id` |
| T7-04 | `chat_messages` type=report | Sau Stage 7 | 1 doc `type=report` với `content` = full markdown |
| T7-05 | LLM fallback | Mock LLM raise Exception | `llm_fallback=true`; report vẫn ghi với fallback text |
| T7-06 | PDF sinh được | Session completed | `generate_pdf(session_id)` trả bytes; không exception |
| T7-07 | PDF nội dung đúng | PDF bytes | Có header session, ETL table, signal card, LLM report |
| T7-08 | Session `completed` sau report_done | Orchestrator nhận `report_done` | `analysis_sessions.status = "completed"` |

```bash
pytest tests/test_insight.py tests/test_pdf.py -v
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] `src/pipeline/insight/worker.py` stream LLM token vào `session:{id}:events`
- [ ] Mỗi `llm_token` emit ngay khi nhận (không buffer)
- [ ] `analysis_reports` ghi đầy đủ field sau stream kết thúc
- [ ] `chat_messages` type=report ghi full markdown
- [ ] `report_done` emit với `report_id`
- [ ] LLM fallback hoạt động — session vẫn đạt `completed`
- [ ] `generate_pdf()` sinh PDF có header + ETL table + signal + report
- [ ] Orchestrator nhận `report_done` → update `analysis_sessions.status=completed`
- [ ] FR-08 hoàn chỉnh; T7-01 → T7-08 pass

---

*[← P6 — Orchestrator](phase-06-orchestrator.md) · [P8 — FastAPI REST + WebSocket →](phase-08-api-websocket.md)*
