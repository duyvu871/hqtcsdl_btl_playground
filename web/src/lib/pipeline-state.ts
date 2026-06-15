import type { WsEvent } from "../schemas/ws-event";
import type { ChatMessage } from "../schemas/message";

/** Aggregate per-stage — mirror backend worker emit format. */
export type StageAgg = {
  started: number;
  completed: number;
  failed: number;
  recordsOut: number;
  meta: Record<string, unknown>;
  errorMsg?: string;
};

export type StageMap = Record<string, StageAgg>;

export type RowStatus = "pending" | "running" | "done" | "failed";

export type TimelineRow = {
  stepNum: number;
  stage: string;
  label: string;
  description: string;
  status: RowStatus;
  pct: number;
  records?: number;
  detail?: string;
  errorMsg?: string;
};

export function normalizeStage(raw: unknown): string {
  return String(raw ?? "").toLowerCase();
}

export function emptyStage(): StageAgg {
  return { started: 0, completed: 0, failed: 0, recordsOut: 0, meta: {} };
}

/** Apply một WS control event vào stage map. */
export function applyWsEvent(map: StageMap, event: WsEvent): StageMap {
  const { event_type: type, data } = event;
  if (!type.startsWith("stage_")) return map;

  const stage = normalizeStage(data.stage);
  if (!stage) return map;

  const next = { ...map };
  const agg: StageAgg = { ...(next[stage] ?? emptyStage()) };

  if (type === "stage_started") {
    agg.started += 1;
  } else if (type === "stage_completed") {
    agg.completed += 1;
    agg.recordsOut += Number(data.records_out ?? 0);
    agg.meta = { ...agg.meta, ...data };
  } else if (type === "stage_failed") {
    agg.failed += 1;
    agg.errorMsg = String(data.error ?? data.message ?? "Lỗi không xác định");
  } else if (type === "stage_progress") {
    agg.meta = { ...agg.meta, ...data };
  }

  next[stage] = agg;
  return next;
}

/** Hydrate từ MongoDB history (etl_progress / error messages). */
export function applyHistoryMessage(map: StageMap, msg: ChatMessage): StageMap {
  const meta = msg.metadata ?? {};
  const stage = normalizeStage(meta.stage);
  if (!stage) return map;

  const status = String(
    meta.status ?? (msg.type === "error" ? "stage_failed" : ""),
  );

  const next = { ...map };
  const agg: StageAgg = { ...(next[stage] ?? emptyStage()) };

  if (status === "stage_started") {
    agg.started += 1;
  } else if (status === "stage_completed") {
    agg.completed += 1;
    agg.recordsOut += Number(meta.records_out ?? 0);
    agg.meta = { ...agg.meta, ...meta };
  } else if (status.includes("failed")) {
    agg.failed += 1;
    agg.errorMsg = String(meta.error ?? meta.message ?? msg.content ?? "Lỗi");
  }

  next[stage] = agg;
  return next;
}

export function stageStatus(agg: StageAgg | undefined, stage: string): { status: RowStatus; pct: number } {
  if (!agg) return { status: "pending", pct: 0 };

  if (agg.failed > 0 && agg.completed === 0) {
    return { status: "failed", pct: 0 };
  }
  if (agg.started === 0 && agg.completed === 0) {
    return { status: "pending", pct: 0 };
  }
  if (agg.completed < agg.started) {
    return {
      status: "running",
      pct: Math.max(8, Math.round((agg.completed / agg.started) * 100)),
    };
  }

  // Scoring: chỉ done khi có ít nhất 1 output thành công
  if (stage === "scoring" && agg.recordsOut === 0 && agg.meta.action == null) {
    return { status: "running", pct: 95 };
  }

  return { status: "done", pct: 100 };
}

export function buildDetail(
  stage: string,
  meta: Record<string, unknown>,
  records?: number,
): string | undefined {
  const parts: string[] = [];
  if (records != null && records > 0) {
    parts.push(`${records.toLocaleString()} records`);
  }

  switch (stage) {
    case "ingest": {
      const sources = meta.sources as Record<string, number> | undefined;
      if (sources) {
        parts.push(
          Object.entries(sources)
            .map(([k, v]) => `${k}: ${v}`)
            .join(", "),
        );
      }
      break;
    }
    case "ner": {
      const coins = meta.coins as string[] | undefined;
      if (coins?.length) parts.push(`coins: ${coins.slice(0, 4).join(", ")}`);
      break;
    }
    case "sentiment": {
      const score = meta.sentiment_score as number | undefined;
      const label = meta.sentiment_label as string | undefined;
      if (score != null) {
        const sign = score >= 0 ? "+" : "";
        parts.push(`${sign}${score.toFixed(3)}${label ? ` (${label})` : ""}`);
      }
      break;
    }
    case "influence": {
      const vol = meta.social_volume as number | undefined;
      const w = meta.influence_weight as number | undefined;
      if (vol != null) parts.push(`volume: ${vol}`);
      if (w != null) parts.push(`weight: ${w.toFixed(3)}`);
      break;
    }
    case "scoring": {
      const action = meta.action as string | undefined;
      const alpha = meta.alpha as number | undefined;
      const safety = meta.safety as number | undefined;
      if (action) parts.push(`signal: ${action}`);
      if (alpha != null) parts.push(`α ${alpha}`);
      if (safety != null) parts.push(`safety ${safety}`);
      break;
    }
    case "insight": {
      const sections = meta.sections as number | undefined;
      const fallback = meta.llm_fallback as boolean | undefined;
      if (sections != null) parts.push(`${sections} sections`);
      if (fallback) parts.push("(fallback)");
      break;
    }
  }

  return parts.length ? parts.join(" · ") : undefined;
}

/** Parse description từ planning content nếu metadata thiếu. */
export function planningDescription(msg: ChatMessage): string {
  const fromMeta = msg.metadata?.description;
  if (fromMeta) return String(fromMeta);
  const m = msg.content.match(/^\d+\.\s*\w+\s*—\s*(.+)$/);
  return m?.[1] ?? "";
}

export function buildTimelineRows(
  planning: ChatMessage[],
  stageMap: StageMap,
  opts?: { insightComplete?: boolean; hasSignal?: boolean },
): TimelineRow[] {
  const sorted = [...planning].sort(
    (a, b) => Number(a.metadata?.step ?? 0) - Number(b.metadata?.step ?? 0),
  );

  const rows = sorted.map((p) => {
    const stage = normalizeStage(p.metadata?.stage);
    const stepNum = Number(p.metadata?.step ?? 0);
    const rawName = String(p.metadata?.stage ?? stage);
    const agg = stageMap[stage];

    let { status, pct } = stageStatus(agg, stage);

    if (stage === "scoring" && opts?.hasSignal && status !== "failed") {
      status = "done";
      pct = 100;
    }
    if (stage === "insight" && opts?.insightComplete && status !== "failed") {
      status = "done";
      pct = 100;
    }

    return {
      stepNum,
      stage,
      label: rawName.charAt(0).toUpperCase() + rawName.slice(1),
      description: planningDescription(p),
      status,
      pct,
      records: agg?.recordsOut || undefined,
      detail: agg ? buildDetail(stage, agg.meta, agg.recordsOut || undefined) : undefined,
      errorMsg: agg?.errorMsg,
    };
  });

  // Sequential display: chỉ 1 step active, các step sau chờ
  let blocked = false;
  return rows.map((row) => {
    if (blocked) {
      return { ...row, status: "pending" as RowStatus, pct: 0, detail: undefined };
    }
    if (row.status === "running" || row.status === "failed") {
      blocked = true;
      return row;
    }
    if (row.status === "pending") {
      blocked = true;
      return row;
    }
    return row;
  });
}
