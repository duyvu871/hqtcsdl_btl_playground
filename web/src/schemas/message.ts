import { z } from "zod";

export const ChatMessageSchema = z.object({
  message_id: z.string(),
  session_id: z.string(),
  role: z.enum(["user", "assistant"]),
  type: z.enum([
    "user",
    "planning",
    "etl_progress",
    "signal_card",
    "report",
    "report_done",
    "error",
  ]),
  content: z.string(),
  metadata: z.record(z.unknown()).optional(),
  created_at: z.string(),
});

export type ChatMessage = z.infer<typeof ChatMessageSchema>;
