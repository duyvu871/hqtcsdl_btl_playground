import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { listJobs, runPipeline, pipelineKeys } from "../api/pipeline";

export function usePipelineJobs(limit = 20) {
  return useQuery({
    queryKey: pipelineKeys.jobs,
    queryFn: () => listJobs(limit),
    refetchInterval: 10_000,
  });
}

export function useRunPipeline() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ coin_id, timeframe }: { coin_id?: string; timeframe?: string } = {}) =>
      runPipeline(coin_id, timeframe),
    onSuccess: () => qc.invalidateQueries({ queryKey: pipelineKeys.jobs }),
  });
}
