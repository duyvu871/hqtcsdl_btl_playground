import type { WsEvent } from "../schemas/ws-event";
import type { ChatMessage } from "../schemas/message";

/** Chuẩn hóa metadata — stage luôn lowercase khớp worker backend. */
function normalizeData(data: Record<string, unknown>): Record<string, unknown> {
  const out = { ...data };
  if (out.stage != null) {
    out.stage = String(out.stage).toLowerCase();
  }
  return out;
}

export function wsEventToMessage(event: WsEvent, sessionId: string): ChatMessage | null {
  const now = event.ts ?? new Date().toISOString();
  const data = normalizeData(event.data);

  switch (event.event_type) {
    case "planning_step":
      return {
        message_id: event.id,
        session_id: sessionId,
        role: "assistant",
        type: "planning",
        content: `${data.step}. ${data.stage} — ${data.description ?? ""}`,
        metadata: data,
        created_at: now,
      };
    case "stage_started":
    case "stage_completed":
    case "stage_progress":
      // Timeline đọc từ pipelineStagesAtom — không lưu vào messages
      return null;
    case "stage_failed":
      return {
        message_id: event.id,
        session_id: sessionId,
        role: "assistant",
        type: "error",
        content: `Stage failed: ${data.error ?? "unknown"}`,
        metadata: { ...data, status: "stage_failed" },
        created_at: now,
      };
    case "signal_ready":
      return {
        message_id: event.id,
        session_id: sessionId,
        role: "assistant",
        type: "signal_card",
        content: `Signal ${data.action} — Alpha ${data.alpha} / Safety ${data.safety}`,
        metadata: data,
        created_at: now,
      };
    case "report_done":
      return {
        message_id: event.id,
        session_id: sessionId,
        role: "assistant",
        type: "report_done",
        content: "Báo cáo hoàn tất — bạn có thể tải PDF.",
        metadata: data,
        created_at: now,
      };
    case "llm_token":
    case "session_completed":
      return null;
    default:
      return null;
  }
}

/** WS event types that update pipeline stage map. */
export function isStageEvent(event: WsEvent): boolean {
  return (
    event.event_type === "stage_started" ||
    event.event_type === "stage_completed" ||
    event.event_type === "stage_failed" ||
    event.event_type === "stage_progress"
  );
}
