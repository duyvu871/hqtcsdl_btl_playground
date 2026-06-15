# P9 — Frontend React SPA

> **Tài liệu tham chiếu:** [`kien-truc-he-thong.md`](../kien-truc-he-thong.md) §9 Kiến trúc Web Frontend · §9.1–9.7  
> [`khung-bao-cao.md`](../khung-bao-cao.md) §3.3.5 Thiết kế Web — Luồng người dùng chính

| Thuộc tính | Giá trị |
|------------|---------|
| **Phụ thuộc vào** | [P8 — FastAPI REST + WebSocket](phase-08-api-websocket.md) |
| **FR liên quan** | **FR-11** (Dashboard TradingView) · **FR-12** (Chat phân tích GPT-like) · **FR-13** (Lưu session + mở lại) · **FR-14** (PDF download) · **FR-15** (ETL Monitor) |
| **Điều hướng** | [← P8](phase-08-api-websocket.md) · [P10 →](phase-10-trien-khai-e2e.md) |

---

## 1. Mục tiêu

Xây dựng React 19 SPA với **3 màn hình** (Dashboard, AnalysisChat, EtlMonitor) theo wireframe §3.3.5. Toàn bộ realtime qua WS, server state qua React Query, client state qua Jotai, validation qua Zod.

---

## 2. Công việc & tái sử dụng

### 2.1. Scaffold và stack (§9, §13.6)

```bash
npm create vite@latest web -- --template react-ts
cd web
npm install @mantine/core@^9 @mantine/hooks @mantine/notifications \
  @tanstack/react-query@^5 jotai@^2 zod@^3 \
  lightweight-charts@^4 react-router-dom@^6 \
  @tailwindcss/vite tailwindcss@^4 \
  @mantine/core/styles.css
```

**`web/vite.config.ts`:**
```typescript
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: { proxy: { "/api": "http://localhost:8000", "/ws": { target: "ws://localhost:8000", ws: true } } },
});
```

### 2.2. Cấu trúc thư mục (§13.6)

```text
web/src/
├── main.tsx              # QueryClientProvider + MantineProvider + JotaiProvider → App
├── index.css             # @import "tailwindcss"
├── theme.ts              # Mantine createTheme dark mode
├── schemas/              # Zod schemas
│   ├── session.ts        # SessionSchema, CreateSessionInput
│   ├── message.ts        # ChatMessageSchema
│   ├── market.ts         # OhlcvCandleSchema, TickerSchema
│   └── ws-event.ts       # WsEventSchema (planning_step, etl_progress, …)
├── atoms/                # Jotai atoms
│   ├── market.ts         # selectedCoinAtom, timeframeAtom
│   ├── chat.ts           # chatMessagesAtom, streamingTextAtom
│   └── ws.ts             # wsConnectedAtom
├── api/                  # fetch helpers + query keys
│   ├── sessions.ts
│   ├── market.ts
│   └── pipeline.ts
├── hooks/
│   ├── useAnalysisWs.ts  # WS hook + chatMessagesAtom
│   ├── useMarketOhlcv.ts
│   ├── useMarketTicker.ts
│   ├── useSessions.ts
│   ├── useSessionMessages.ts
│   └── useCreateSession.ts
├── pages/
│   ├── Dashboard.tsx
│   ├── AnalysisChat.tsx
│   └── EtlMonitor.tsx
└── components/
    ├── TradingViewChart.tsx
    ├── TickerBar.tsx
    ├── SessionSidebar.tsx
    ├── AnalyzeButton.tsx
    ├── ChatHeader.tsx
    ├── MessageList.tsx
    ├── ChatMessage.tsx
    ├── PlanningSteps.tsx
    ├── EtlProgressCard.tsx
    ├── SignalCard.tsx
    └── ChatInput.tsx
```

### 2.3. Zod schemas (§9.4)

```typescript
// web/src/schemas/session.ts
export const CreateSessionInput = z.object({
  coin_id: z.enum(["BTC","ETH","SOL","BNB","XRP","ADA","DOGE","AVAX","DOT","MATIC"]),
  timeframe: z.enum(["15m","30m","1h","4h","1d"]),
});

export const ChatMessageSchema = z.object({
  message_id: z.string().uuid(),
  session_id: z.string().uuid(),
  role: z.enum(["user","assistant"]),
  type: z.enum(["user","planning","etl_progress","signal_card","report","report_done","error"]),
  content: z.string(),
  metadata: z.record(z.unknown()).optional(),
  created_at: z.string().datetime(),
});

export const OhlcvCandleSchema = z.object({
  time: z.number(), open: z.number(), high: z.number(),
  low: z.number(), close: z.number(), volume: z.number().optional(),
});
```

### 2.4. Jotai atoms (§9.3)

```typescript
// atoms/market.ts
export const selectedCoinAtom = atomWithStorage("selectedCoin", "BTC");
export const timeframeAtom    = atomWithStorage("timeframe", "1h");

// atoms/chat.ts
export const chatMessagesAtom  = atom<ChatMessage[]>([]);
export const streamingTextAtom = atom<string>("");

// atoms/ws.ts
export const wsConnectedAtom = atom(false);
```

### 2.5. `useAnalysisWs` hook (§9.5)

```typescript
export function useAnalysisWs(sessionId: string, lastId = "0") {
  const setMessages    = useSetAtom(chatMessagesAtom);
  const setStreaming   = useSetAtom(streamingTextAtom);
  const setConnected   = useSetAtom(wsConnectedAtom);

  useEffect(() => {
    const ws = new WebSocket(`ws://localhost:8000/ws/analysis/${sessionId}?last_id=${lastId}`);
    ws.onopen  = () => setConnected(true);
    ws.onclose = () => setConnected(false);
    ws.onmessage = ({ data }) => {
      const event = WsEventSchema.parse(JSON.parse(data));
      switch (event.event_type) {
        case "llm_token":
          setStreaming(prev => prev + event.data.token); break;
        case "report_done":
          setMessages(prev => [...prev, flushStreamingMessage(event)]); break;
        default:
          setMessages(prev => [...prev, wsEventToMessage(event)]);
      }
    };
    return () => ws.close();
  }, [sessionId]);
}
```

### 2.6. Ba màn hình chính

**`Dashboard.tsx`** (wireframe §3.3.5):
- `TradingViewChart` — lightweight-charts candlestick + volume
- `TickerBar` — giá realtime, React Query `refetchInterval: 5000`
- `SessionSidebar` — danh sách sessions, React Query `useSessions()`
- `AnalyzeButton` — `useCreateSession()` mutation → navigate `/analysis/:id`
- Coin selector (Jotai `selectedCoinAtom`) + Timeframe selector

**`AnalysisChat.tsx`** (ChatGPT-like):
- `useAnalysisWs(sessionId)` — append events vào `chatMessagesAtom`
- `MessageList` — render từng message theo `type`:
  - `planning` → `PlanningSteps` numbered list
  - `etl_progress` → `EtlProgressCard` (progress bar + stats)
  - `signal_card` → `SignalCard` (BUY/HOLD + alpha + safety)
  - `report` → markdown streaming (`streamingTextAtom`)
  - `report_done` → nút "Tải PDF" + disclaimer
- `ChatInput` — follow-up question

**`EtlMonitor.tsx`**:
- React Query `usePipelineJobs()` — danh sách job
- WS `/ws/pipeline` — live progress per stage
- Nút "Run All" → `POST /api/v1/pipeline/run`
- Bảng job detail: stage | status | records_in/out | duration_ms

---

## 3. Kiểm thử

| Test ID | Mô tả | Lệnh | Kết quả mong đợi |
|---------|-------|------|------------------|
| T9-01 | Zod parse `ChatMessageSchema` | Unit test | Invalid message throw ZodError; valid parse thành công |
| T9-02 | `CreateSessionInput` validate | `coin_id="INVALID"` | ZodError; `coin_id="BTC"` → pass |
| T9-03 | TradingView chart render | Mở `/dashboard` | Candlestick chart hiển thị; không lỗi console |
| T9-04 | Sidebar sessions load | `useSessions()` mock | Hiển thị danh sách; click → navigate |
| T9-05 | WS connect + message append | Mock WS server | `chatMessagesAtom` append khi nhận event |
| T9-06 | LLM token stream render | Sequence `llm_token` events | `streamingTextAtom` tăng dần; cuối flush vào messages |
| T9-07 | Signal card render | `signal_ready` event | `SignalCard` hiển thị BUY/HOLD + alpha + safety |
| T9-08 | PDF button hiện | `report_done` event | Nút "Tải PDF" enabled; click → `GET /export/pdf` |
| T9-09 | Mở lại session cũ | Navigate `/analysis/old-id` | `useSessionMessages()` render lịch sử từ MongoDB |
| **TC-10** | E2E full flow | Playwright: chọn BTC 1h → Phân tích → chat → PDF | Session tạo; 7 planning; ETL cards; signal; report stream; PDF download |

```bash
# Unit + component test
cd web && npm run test

# E2E Playwright
npx playwright test tests/e2e/full-flow.spec.ts
```

---

## 4. Kết quả cần đạt (DoD)

- [ ] 3 route hoạt động: `/dashboard`, `/analysis/:sessionId`, `/etl`
- [ ] TradingView chart render OHLCV từ API
- [ ] Chat UI nhận WS events và render đúng component theo type
- [ ] LLM token stream append real-time (không batch)
- [ ] `streamingTextAtom` flush vào `chatMessagesAtom` khi `report_done`
- [ ] Mở lại session cũ → render đầy đủ lịch sử từ MongoDB (read-only khi completed)
- [ ] Nút PDF → download file; nút enabled chỉ sau `report_done`
- [ ] TC-10 E2E Playwright pass
- [ ] Zod parse fail-fast khi API lệch schema (lỗi rõ ràng trong console)
- [ ] Dark mode Mantine theme đồng nhất trên 3 màn hình

---

*[← P8 — FastAPI REST + WebSocket](phase-08-api-websocket.md) · [P10 — Triển khai E2E →](phase-10-trien-khai-e2e.md)*
