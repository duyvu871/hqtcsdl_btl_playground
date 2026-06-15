const API = "/api/v1";

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const text = await res.text();
    throw new Error(`${res.status}: ${text}`);
  }
  return res.json() as Promise<T>;
}

export const sessionKeys = {
  all: ["sessions"] as const,
  detail: (id: string) => ["sessions", id] as const,
  messages: (id: string) => ["sessions", id, "messages"] as const,
};

export async function listSessions(limit = 20) {
  return fetchJson<{ sessions: unknown[] }>(`${API}/analysis/sessions?limit=${limit}`);
}

export async function createSession(coin_id: string, timeframe: string) {
  return fetchJson<{ session_id: string; job_id: string }>(`${API}/analysis/sessions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ coin_id, timeframe }),
  });
}

export async function getSessionMessages(sessionId: string) {
  return fetchJson<{ messages: unknown[] }>(`${API}/analysis/sessions/${sessionId}/messages`);
}

export function pdfUrl(sessionId: string) {
  return `${API}/analysis/sessions/${sessionId}/export/pdf`;
}

export async function postFollowUp(sessionId: string, content: string) {
  return fetchJson<{ message_id: string }>(`${API}/analysis/sessions/${sessionId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ content }),
  });
}
