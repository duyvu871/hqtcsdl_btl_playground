import { useQuery } from "@tanstack/react-query";
import { fetchOhlcv, marketKeys } from "../api/market";

export function useMarketOhlcv(coin: string, interval: string) {
  return useQuery({
    queryKey: marketKeys.ohlcv(coin, interval),
    queryFn: () => fetchOhlcv(coin, interval),
    staleTime: 60_000,
  });
}
