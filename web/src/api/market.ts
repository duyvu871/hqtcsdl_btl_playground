import { OhlcvResponseSchema, TickerSchema } from "../schemas/market";

const API = "/api/v1";

export const marketKeys = {
  ohlcv: (coin: string, interval: string) => ["ohlcv", coin, interval] as const,
  ticker: (coin: string) => ["ticker", coin] as const,
};

export async function fetchOhlcv(coin: string, interval: string, limit = 48) {
  const res = await fetch(`${API}/market/ohlcv?coin=${coin}&interval=${interval}&limit=${limit}`);
  if (!res.ok) throw new Error(`OHLCV ${res.status}`);
  const json = await res.json();
  return OhlcvResponseSchema.parse(json);
}

export async function fetchTicker(coin: string) {
  const res = await fetch(`${API}/market/ticker?coin=${coin}`);
  if (!res.ok) throw new Error(`Ticker ${res.status}`);
  const json = await res.json();
  return TickerSchema.parse(json);
}
