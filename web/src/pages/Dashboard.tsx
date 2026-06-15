import { Group, Select, Stack, Title } from "@mantine/core";
import { useAtom } from "jotai";
import { selectedCoinAtom, timeframeAtom } from "../atoms/market";
import { COIN_IDS, TIMEFRAMES } from "../schemas/session";
import { useMarketOhlcv } from "../hooks/useMarketOhlcv";
import { useMarketTicker } from "../hooks/useMarketTicker";
import { useSessions } from "../hooks/useSessions";
import { TradingViewChart } from "../components/TradingViewChart";
import { TickerBar } from "../components/TickerBar";
import { SessionSidebar } from "../components/SessionSidebar";
import { AnalyzeButton } from "../components/AnalyzeButton";

export function Dashboard() {
  const [coin, setCoin] = useAtom(selectedCoinAtom);
  const [timeframe, setTimeframe] = useAtom(timeframeAtom);
  const ohlcv = useMarketOhlcv(coin, timeframe);
  const ticker = useMarketTicker(coin);
  const sessions = useSessions();

  return (
    <Group align="stretch" gap={0} style={{ minHeight: "calc(100vh - 52px)" }}>
      <SessionSidebar sessions={sessions.data ?? []} loading={sessions.isLoading} />
      <Stack gap={0} style={{ flex: 1 }}>
        <TickerBar coin={coin} ticker={ticker.data} loading={ticker.isLoading} />
        <Group p="md" justify="space-between">
          <Title order={4}>Dashboard</Title>
          <Group>
            <Select
              data={[...COIN_IDS]}
              value={coin}
              onChange={(v) => v && setCoin(v)}
              w={100}
            />
            <Select
              data={[...TIMEFRAMES]}
              value={timeframe}
              onChange={(v) => v && setTimeframe(v)}
              w={100}
            />
            <AnalyzeButton />
          </Group>
        </Group>
        <TradingViewChart candles={ohlcv.data?.candles ?? []} />
      </Stack>
    </Group>
  );
}
