import { useQuery } from "@tanstack/react-query";
import { fetchTicker, marketKeys } from "../api/market";

export function useMarketTicker(coin: string) {
  return useQuery({
    queryKey: marketKeys.ticker(coin),
    queryFn: () => fetchTicker(coin),
    refetchInterval: 5_000,
  });
}
