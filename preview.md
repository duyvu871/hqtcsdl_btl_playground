Đây là một phân tích rất tốt và **đúng với những gì chúng ta đang thiết kế**. Mình sẽ đối chiếu thẳng với hệ thống đã build và chỉ ra chỗ cần bổ sung.

---

## Điều document nói đúng nhất

> *"80% chất lượng nằm ở feature engineering, không phải AI"*

Trong thiết kế trước, pipeline của chúng ta đã có `Validate → Normalize → Enrich` nhưng **còn thiếu 1 layer giữa Enrich và Agent** — đó là **Signal Layer**. Đây là điểm quan trọng nhất cần thêm vào.

---

## Mapping với thiết kế hiện tại

| Document | Thiết kế hiện tại | Trạng thái |
|---|---|---|
| Data Layer | `BasePipeline` + `MarketEvent` | ✅ Có rồi |
| Feature Layer | `enrichers.py` (RSI, MACD) | ✅ Có rồi |
| **Signal Layer** | **Chưa có** | ❌ Cần thêm |
| Serving Layer | `query_api.py` | ✅ Có rồi |
| Agent Layer | LangChain tools | ⚠️ Đang nhận sai input |

Vấn đề cụ thể: tools hiện tại trả `raw candles + indicators` cho LLM. Đúng ra phải trả `structured signals + confidence`.

---

## Cái cần thêm: `SignalEngine`

```python
# pipeline/signals/engine.py

from dataclasses import dataclass
from ..core.schema import MarketEvent

@dataclass
class TradingSignal:
    symbol:     str
    signal:     str          # "overbought" | "oversold" | "breakout" | "accumulation" | "neutral"
    strength:   float        # 0.0 – 1.0
    timeframe:  str          # "1h" | "4h" | "1d"
    reason:     str          # human-readable, AI sẽ dùng cái này
    risk_level: str          # "low" | "medium" | "high"
    sources:    list[str]    # ["rsi", "macd", "volume"] — provenance

class SignalEngine:
    """
    Rule-based. Deterministic. Không có AI ở đây.
    Input: enriched MarketEvent
    Output: TradingSignal
    """

    def evaluate(self, event: MarketEvent) -> TradingSignal:
        ind = event.data.get("indicators", {})
        data = event.data

        signals = []
        reasons = []
        sources = []

        rsi = ind.get("rsi")
        macd = ind.get("macd")
        macd_signal = ind.get("macd_signal")
        bb_upper = ind.get("bb_upper")
        bb_lower = ind.get("bb_lower")
        close = data.get("c")

        # ── RSI ──────────────────────────────────────────────────────────────
        if rsi:
            sources.append("rsi")
            if rsi > 70:
                signals.append(("overbought", 0.7))
                reasons.append(f"RSI {rsi:.1f} — vùng overbought")
            elif rsi < 30:
                signals.append(("oversold", 0.7))
                reasons.append(f"RSI {rsi:.1f} — vùng oversold")
            elif 45 <= rsi <= 55:
                signals.append(("neutral", 0.3))

        # ── MACD ─────────────────────────────────────────────────────────────
        if macd and macd_signal:
            sources.append("macd")
            if macd > macd_signal and macd > 0:
                signals.append(("bullish", 0.6))
                reasons.append("MACD cắt lên trên signal line")
            elif macd < macd_signal and macd < 0:
                signals.append(("bearish", 0.6))
                reasons.append("MACD cắt xuống dưới signal line")

        # ── Bollinger Bands ───────────────────────────────────────────────────
        if bb_upper and bb_lower and close:
            sources.append("bollinger")
            if close > bb_upper:
                signals.append(("overbought", 0.5))
                reasons.append(f"Giá {close} vượt BB upper {bb_upper:.1f}")
            elif close < bb_lower:
                signals.append(("oversold", 0.5))
                reasons.append(f"Giá {close} dưới BB lower {bb_lower:.1f}")

        # ── Tổng hợp: lấy signal có strength cao nhất ────────────────────────
        if not signals:
            return TradingSignal(
                symbol=event.symbol, signal="neutral", strength=0.2,
                timeframe="1h", reason="Không có tín hiệu rõ", 
                risk_level="low", sources=[]
            )

        dominant = max(signals, key=lambda x: x[1])
        strength = sum(s[1] for s in signals if s[0] == dominant[0]) / len(signals)

        return TradingSignal(
            symbol=event.symbol,
            signal=dominant[0],
            strength=round(strength, 2),
            timeframe="1h",
            reason=" | ".join(reasons),
            risk_level="high" if strength > 0.7 else "medium" if strength > 0.4 else "low",
            sources=sources,
        )
```

---

## Cập nhật `serving/query_api.py` — trả `TradingContext` thay vì raw data

```python
# serving/query_api.py

from dataclasses import asdict
from ..signals.engine import SignalEngine, TradingSignal

signal_engine = SignalEngine()

async def get_trading_context(symbol: str, risk_profile: str = "medium") -> dict:
    """
    Đây là thứ AI agent nhận được.
    Không có raw candles. Không có số liệu thô.
    Chỉ có structured signals + context để reason.
    """
    # Lấy từ serving layer
    ohlcv_event  = await get_latest_event(symbol, EventType.OHLCV)
    ob_event     = await get_latest_event(symbol, EventType.ORDERBOOK)
    news_events  = await get_history(symbol, EventType.NEWS, count=5)
    sent_event   = await get_latest_event(symbol, EventType.SENTIMENT)

    # Chuyển thành signals — deterministic, rule-based
    price_signal = signal_engine.evaluate(ohlcv_event) if ohlcv_event else None

    return {
        "symbol": symbol,
        "risk_profile": risk_profile,

        # Price action
        "price": {
            "current":  ohlcv_event.data["c"] if ohlcv_event else None,
            "change_1h": _pct_change(ohlcv_event),
            "signal":   asdict(price_signal) if price_signal else None,
        },

        # Order book
        "market_depth": {
            "spread":    ob_event.data.get("spread") if ob_event else None,
            "imbalance": ob_event.data.get("imbalance") if ob_event else None,
            # imbalance > 0.6 = nhiều buyer; < 0.4 = nhiều seller
        },

        # Sentiment
        "sentiment": {
            "score":       sent_event.data.get("score") if sent_event else None,
            "fear_greed":  sent_event.data.get("fear_greed") if sent_event else None,
            "label":       sent_event.data.get("label") if sent_event else None,
        },

        # News headlines (tiêu đề + sentiment, không phải nội dung)
        "recent_news": [
            {"title": e.data["title"], "sentiment": e.data["sentiment"]}
            for e in news_events
        ] if news_events else [],
    }
```

---

## Cập nhật AI Agent tool — nhận `TradingContext`, không phải raw data

```python
# ai-service/app/agent/tools.py

@tool
async def get_trading_advice(symbol: str, risk_profile: str = "medium") -> dict:
    """
    Lấy toàn bộ trading context đã được pipeline xử lý.
    Tool này KHÔNG tính indicator, KHÔNG parse raw data.
    """
    return await get_trading_context(symbol, risk_profile)
```

```python
# ai-service/app/agent/agent.py  — system prompt cập nhật

SYSTEM_PROMPT = """Bạn là chuyên gia phân tích trading crypto.

Bạn nhận được một TradingContext đã được xử lý bởi hệ thống pipeline.
Context này bao gồm:
- price.signal: tín hiệu kỹ thuật (overbought/oversold/bullish/bearish/neutral)
- price.signal.strength: độ mạnh 0-1
- price.signal.reason: lý do rule-based
- market_depth.imbalance: cán cân mua/bán
- sentiment: tâm lý thị trường
- recent_news: tin tức gần nhất

Nhiệm vụ của bạn:
1. TỔNG HỢP các signals — không tính lại
2. GIẢI THÍCH quyết định bằng ngôn ngữ tự nhiên
3. Đưa ra recommendation với format:
   - action: "long" | "short" | "wait" | "exit"
   - confidence: 0.0 – 1.0  
   - reason: giải thích ngắn gọn
   - risk_note: lưu ý rủi ro

QUAN TRỌNG: Nếu signal.strength < 0.4 hoặc các signals mâu thuẫn nhau, 
luôn khuyến nghị "wait".
"""
```

---

## Pipeline flow hoàn chỉnh (cập nhật theo document)

```
[Exchange WS / REST]
        ↓
[BasePipeline.ingest()]        ← thu thập raw
        ↓
[BasePipeline.validate()]      ← loại data xấu → DLQ
        ↓
[BasePipeline.normalize()]     ← → MarketEvent (canonical schema)
        ↓
[BasePipeline.enrich()]        ← tính indicators (RSI, MACD, BB)
        ↓
[Redis Streams + TimescaleDB]  ← serving layer
        ↓
[SignalEngine.evaluate()]      ← rule-based, deterministic  ← MỚI THÊM
        ↓
[get_trading_context()]        ← structured context cho agent
        ↓
[AI Agent]                     ← chỉ reason + communicate
        ↓
[Frontend Dashboard]
```

---

## MVP theo đúng phase document gợi ý

```
Phase 1 (tuần 1–2):
  ✅ BinanceOHLCVPipeline → MarketEvent → Redis
  ✅ SignalEngine với RSI + MACD

Phase 2 (tuần 3–4):
  ✅ Thêm OrderbookPipeline + NewsPipeline
  ✅ get_trading_context() hoàn chỉnh
  ✅ API endpoint /context/:symbol

Phase 3 (tuần 5+):
  ✅ Kết nối AI Agent với TradingContext
  ✅ Dashboard hiển thị signals + AI advice
```

---

Document này tốt ở chỗ nhắc đúng điều quan trọng nhất: **AI agent chỉ là lớp cuối, không phải trung tâm**. Thiết kế của chúng ta về cơ bản đã đúng hướng — chỉ cần bổ sung `SignalEngine` như một lớp tường lửa giữa data và AI, đảm bảo LLM không bao giờ nhận raw numbers mà không có context.