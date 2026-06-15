const API = "/api/v1";

export const pipelineKeys = {
  jobs: ["pipeline", "jobs"] as const,
  job: (id: string) => ["pipeline", "jobs", id] as const,
  stats: ["pipeline", "stats"] as const,
};

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) throw new Error(`${res.status}`);
  return res.json() as Promise<T>;
}

export async function listJobs(limit = 20) {
  return fetchJson<{ jobs: unknown[] }>(`${API}/pipeline/jobs?limit=${limit}`);
}

export async function runPipeline(coin_id = "BTC", timeframe = "1h") {
  return fetchJson<{ job_id: string; status: string; session_id: string }>(
    `${API}/pipeline/run`,
    {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ coin_id, timeframe }),
    },
  );
}

export async function getPipelineStats() {
  return fetchJson<Record<string, number>>(`${API}/pipeline/stats`);
}
