import type { ChatMessage } from "../schemas/message";

/** Khóa dedupe — planning dùng step, còn lại dùng message_id. */
export function messageDedupeKey(m: ChatMessage): string {
  if (m.type === "planning") {
    const step = m.metadata?.step;
    if (step != null) return `planning:step:${step}`;
  }
  return m.message_id;
}

export function appendMessage(prev: ChatMessage[], msg: ChatMessage): ChatMessage[] {
  const key = messageDedupeKey(msg);
  const idx = prev.findIndex((m) => messageDedupeKey(m) === key);
  if (idx >= 0) {
    // Planning: merge metadata mới từ WS (có description) vào bản history
    if (msg.type === "planning") {
      const merged: ChatMessage = {
        ...prev[idx],
        metadata: { ...prev[idx].metadata, ...msg.metadata },
        content: msg.content || prev[idx].content,
      };
      const out = [...prev];
      out[idx] = merged;
      return out;
    }
    return prev;
  }
  return [...prev, msg].sort(
    (a, b) => new Date(a.created_at).getTime() - new Date(b.created_at).getTime(),
  );
}

export function mergeMessages(base: ChatMessage[], incoming: ChatMessage[]): ChatMessage[] {
  let out = [...base];
  for (const msg of incoming) {
    out = appendMessage(out, msg);
  }
  return out;
}

export type DisplayItem =
  | { kind: "planning_group"; steps: ChatMessage[] }
  | { kind: "message"; message: ChatMessage };

/** Gom các planning liên tiếp thành 1 card. */
export function groupForDisplay(messages: ChatMessage[]): DisplayItem[] {
  const items: DisplayItem[] = [];
  let planning: ChatMessage[] = [];

  const flushPlanning = () => {
    if (!planning.length) return;
    items.push({
      kind: "planning_group",
      steps: [...planning].sort(
        (a, b) => Number(a.metadata?.step ?? 0) - Number(b.metadata?.step ?? 0),
      ),
    });
    planning = [];
  };

  for (const m of messages) {
    if (m.type === "planning") {
      planning.push(m);
    } else {
      flushPlanning();
      items.push({ kind: "message", message: m });
    }
  }
  flushPlanning();
  return items;
}
