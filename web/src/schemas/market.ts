import { z } from "zod";

export const OhlcvCandleSchema = z.object({
  time: z.number(),
  open: z.number(),
  high: z.number(),
  low: z.number(),
  close: z.number(),
  volume: z.number().optional(),
});

export type OhlcvCandle = z.infer<typeof OhlcvCandleSchema>;

export const OhlcvResponseSchema = z.object({
  coin: z.string(),
  interval: z.string(),
  candles: z.array(OhlcvCandleSchema),
});

export const TickerSchema = z.object({
  coin: z.string(),
  last: z.number(),
  change_pct: z.number(),
  volume: z.number(),
});

export type Ticker = z.infer<typeof TickerSchema>;
