import { Paper, Text, Progress, Group, Badge } from "@mantine/core";
import type { ChatMessage } from "../schemas/message";

type Props = { message: ChatMessage };

export function EtlProgressCard({ message }: Props) {
  const meta = message.metadata ?? {};
  const stage = String(meta.stage ?? "—");
  const status = String(meta.status ?? "running");
  const pct = Number(meta.pct ?? (status === "stage_completed" ? 100 : 50));
  const recordsOut = meta.records_out;

  return (
    <Paper p="md" radius="md" bg="dark.6" withBorder>
      <Group justify="space-between" mb="xs">
        <Text fw={600}>ETL — {stage}</Text>
        <Badge size="sm" color={status.includes("failed") ? "red" : "cyan"}>
          {status.replace("stage_", "")}
        </Badge>
      </Group>
      <Progress value={pct} color="cyan" size="sm" mb="xs" />
      {recordsOut != null && (
        <Text size="xs" c="dimmed">records out: {String(recordsOut)}</Text>
      )}
    </Paper>
  );
}
