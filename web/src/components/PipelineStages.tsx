import { Paper, Text, Progress, Group, Badge, Stack, Box, ThemeIcon } from "@mantine/core";
import {
  IconCheck,
  IconLoader2,
  IconClock,
  IconAlertTriangle,
} from "@tabler/icons-react";
import type { ChatMessage } from "../schemas/message";

const STAGE_ORDER = ["ingest", "filter", "sentiment", "score", "insight"];

const STAGE_LABEL: Record<string, string> = {
  ingest: "Thu thập dữ liệu",
  filter: "Lọc spam & nhiễu",
  sentiment: "Phân tích cảm xúc",
  score: "Scoring & Signal",
  insight: "Tổng hợp insight",
};

type StageInfo = {
  stage: string;
  status: string;
  pct: number;
  records_out?: number;
};

function buildStages(messages: ChatMessage[]): StageInfo[] {
  const map = new Map<string, StageInfo>();

  for (const msg of messages) {
    const meta = msg.metadata ?? {};
    const stage = String(meta.stage ?? "unknown");
    const rawStatus = String(meta.status ?? "running");

    let pct: number;
    if (rawStatus === "stage_completed") pct = 100;
    else if (rawStatus === "stage_started") pct = 10;
    else pct = Number(meta.pct ?? 50);

    const existing = map.get(stage);
    map.set(stage, {
      stage,
      status: rawStatus,
      pct: Math.max(existing?.pct ?? 0, pct),
      records_out: (meta.records_out as number | undefined) ?? existing?.records_out,
    });
  }

  return [...map.values()].sort((a, b) => {
    const ai = STAGE_ORDER.indexOf(a.stage);
    const bi = STAGE_ORDER.indexOf(b.stage);
    return (ai === -1 ? 999 : ai) - (bi === -1 ? 999 : bi);
  });
}

function statusColor(status: string): string {
  if (status.includes("failed")) return "red";
  if (status === "stage_completed") return "teal";
  if (status === "stage_started" || status === "stage_progress") return "cyan";
  return "gray";
}

function StatusIcon({ status }: { status: string }) {
  if (status === "stage_completed")
    return (
      <ThemeIcon color="teal" variant="light" size="sm" radius="xl">
        <IconCheck size={12} />
      </ThemeIcon>
    );
  if (status.includes("failed"))
    return (
      <ThemeIcon color="red" variant="light" size="sm" radius="xl">
        <IconAlertTriangle size={12} />
      </ThemeIcon>
    );
  if (status === "stage_started" || status === "stage_progress")
    return (
      <ThemeIcon color="cyan" variant="light" size="sm" radius="xl">
        <IconLoader2 size={12} style={{ animation: "spin 1s linear infinite" }} />
      </ThemeIcon>
    );
  return (
    <ThemeIcon color="gray" variant="light" size="sm" radius="xl">
      <IconClock size={12} />
    </ThemeIcon>
  );
}

type Props = { messages: ChatMessage[] };

export function PipelineStages({ messages }: Props) {
  const stages = buildStages(messages);

  return (
    <Paper p="lg" radius="md" bg="dark.7" withBorder>
      <Group gap="xs" mb="md">
        <Box
          w={24}
          h={24}
          style={{
            borderRadius: "50%",
            background: "#1971c2",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 700,
            color: "#fff",
            flexShrink: 0,
          }}
        >
          2
        </Box>
        <Text fw={700} size="sm" tt="uppercase" c="dimmed" style={{ letterSpacing: "0.05em" }}>
          Thực thi Pipeline
        </Text>
      </Group>

      <Stack gap="sm">
        {stages.map((s) => (
          <Box key={s.stage}>
            <Group justify="space-between" mb={4}>
              <Group gap="xs">
                <StatusIcon status={s.status} />
                <Text size="sm" fw={500}>
                  {STAGE_LABEL[s.stage] ?? s.stage}
                </Text>
              </Group>
              <Group gap="xs">
                {s.records_out != null && (
                  <Text size="xs" c="dimmed">
                    {s.records_out.toLocaleString()} records
                  </Text>
                )}
                <Badge size="xs" color={statusColor(s.status)} variant="light">
                  {s.status.replace("stage_", "")}
                </Badge>
                <Text size="xs" c="dimmed" miw={32} ta="right">
                  {s.pct}%
                </Text>
              </Group>
            </Group>
            <Progress
              value={s.pct}
              color={statusColor(s.status)}
              size="xs"
              radius="xl"
              animated={s.status !== "stage_completed" && !s.status.includes("failed")}
            />
          </Box>
        ))}
      </Stack>
    </Paper>
  );
}
