import { z } from "zod";

export const WsEventSchema = z.object({
  id: z.string(),
  event_type: z.string(),
  session_id: z.string().optional(),
  job_id: z.string().optional(),
  data: z.record(z.unknown()).default({}),
  ts: z.string().optional(),
});

export type WsEvent = z.infer<typeof WsEventSchema>;
