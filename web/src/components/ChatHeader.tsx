import { Group, Text, Badge } from "@mantine/core";
import { useAtomValue } from "jotai";
import { wsConnectedAtom } from "../atoms/ws";

type Props = { sessionId: string; coin?: string; timeframe?: string };

export function ChatHeader({ sessionId, coin, timeframe }: Props) {
  const connected = useAtomValue(wsConnectedAtom);

  return (
    <Group justify="space-between" p="md" style={{ borderBottom: "1px solid #21262d" }}>
      <div>
        <Text fw={700}>Phân tích {coin ?? "—"} · {timeframe ?? "—"}</Text>
        <Text size="xs" c="dimmed">{sessionId}</Text>
      </div>
      <Badge color={connected ? "teal" : "gray"} variant="dot">
        {connected ? "Live" : "Offline"}
      </Badge>
    </Group>
  );
}
