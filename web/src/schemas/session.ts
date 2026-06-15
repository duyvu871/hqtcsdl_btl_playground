import { z } from "zod";

export const COIN_IDS = [
  "BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "MATIC",
] as const;

export const TIMEFRAMES = ["15m", "30m", "1h", "4h", "1d"] as const;

export const CreateSessionInput = z.object({
  coin_id: z.enum(COIN_IDS),
  timeframe: z.enum(TIMEFRAMES),
});

export type CreateSessionInputType = z.infer<typeof CreateSessionInput>;

export const SessionSchema = z.object({
  session_id: z.string(),
  coin_id: z.string(),
  timeframe: z.string(),
  job_id: z.string().optional(),
  status: z.string().optional(),
  created_at: z.string().optional(),
});

export type Session = z.infer<typeof SessionSchema>;
