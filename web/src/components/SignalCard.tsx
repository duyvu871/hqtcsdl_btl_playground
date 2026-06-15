import { Paper, Text, Group, Badge, Stack } from "@mantine/core";

type Props = {
  content: string;
  metadata?: Record<string, unknown>;
};

export function SignalCard({ content, metadata = {} }: Props) {
  const action = String(metadata.action ?? "HOLD");
  const coinId = metadata.coin_id != null ? String(metadata.coin_id) : null;
  const alpha = metadata.alpha ?? metadata.galaxy_alpha_score ?? "—";
  const safety = metadata.safety ?? metadata.galaxy_safety_score ?? "—";
  const color = action === "BUY" ? "teal" : action === "SELL" ? "red" : "yellow";

  return (
    <Paper p="md" radius="md" bg="dark.6" withBorder>
      <Group mb="sm">
        <Text fw={700}>Tín hiệu Scoring{coinId ? ` · ${coinId}` : ""}</Text>
        <Badge size="lg" color={color}>{action}</Badge>
      </Group>
      <Stack gap={4}>
        <Text size="sm">{content}</Text>
        <Text size="sm">Alpha: <strong>{String(alpha)}</strong></Text>
        <Text size="sm">Safety: <strong>{String(safety)}</strong></Text>
        {metadata.target != null && (
          <Text size="xs" c="dimmed">Target: {String(metadata.target)}</Text>
        )}
        {metadata.stop != null && (
          <Text size="xs" c="dimmed">Stop: {String(metadata.stop)}</Text>
        )}
      </Stack>
    </Paper>
  );
}
