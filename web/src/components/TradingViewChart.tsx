import { useEffect, useRef } from "react";
import { createChart, type IChartApi, type ISeriesApi, type CandlestickData } from "lightweight-charts";
import { Box, Text } from "@mantine/core";
import type { OhlcvCandle } from "../schemas/market";

type Props = {
  candles: OhlcvCandle[];
  height?: number;
};

export function TradingViewChart({ candles, height = 360 }: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const chartRef = useRef<IChartApi | null>(null);
  const seriesRef = useRef<ISeriesApi<"Candlestick"> | null>(null);

  useEffect(() => {
    if (!containerRef.current) return;

    const chart = createChart(containerRef.current, {
      height,
      layout: { background: { color: "#161b22" }, textColor: "#c9d1d9" },
      grid: { vertLines: { color: "#21262d" }, horzLines: { color: "#21262d" } },
    });
    const series = chart.addCandlestickSeries({
      upColor: "#26a69a",
      downColor: "#ef5350",
      borderVisible: false,
      wickUpColor: "#26a69a",
      wickDownColor: "#ef5350",
    });

    chartRef.current = chart;
    seriesRef.current = series;

    const ro = new ResizeObserver(() => {
      if (containerRef.current) {
        chart.applyOptions({ width: containerRef.current.clientWidth });
      }
    });
    ro.observe(containerRef.current);

    return () => {
      ro.disconnect();
      chart.remove();
      chartRef.current = null;
      seriesRef.current = null;
    };
  }, [height]);

  useEffect(() => {
    if (!seriesRef.current || !candles.length) return;

    const data: CandlestickData[] = candles.map((c) => ({
      time: Math.floor(c.time / 1000) as CandlestickData["time"],
      open: c.open,
      high: c.high,
      low: c.low,
      close: c.close,
    }));
    seriesRef.current.setData(data);
    chartRef.current?.timeScale().fitContent();
  }, [candles]);

  if (!candles.length) {
    return <Text c="dimmed" p="md">Đang tải dữ liệu chart…</Text>;
  }

  return <Box ref={containerRef} style={{ width: "100%" }} />;
}
