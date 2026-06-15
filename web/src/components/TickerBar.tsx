import { Group, Text, Badge } from "@mantine/core";
import type { Ticker } from "../schemas/market";

type Props = { coin: string; ticker?: Ticker; loading?: boolean };

export function TickerBar({ coin, ticker, loading }: Props) {
  const change = ticker?.change_pct ?? 0;
  const color = change >= 0 ? "teal" : "red";

  return (
    <Group gap="lg" p="md" style={{ borderBottom: "1px solid #21262d" }}>
      <Text fw={700} size="xl">{coin}/USDT</Text>
      <Text size="xl" fw={600}>
        {loading ? "…" : `$${(ticker?.last ?? 0).toLocaleString()}`}
      </Text>
      <Badge color={color} variant="light">
        {loading ? "…" : `${change >= 0 ? "+" : ""}${change.toFixed(2)}%`}
      </Badge>
      <Text c="dimmed" size="sm">
        Vol: {loading ? "…" : (ticker?.volume ?? 0).toLocaleString()}
      </Text>
    </Group>
  );
}
