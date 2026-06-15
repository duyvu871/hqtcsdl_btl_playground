import { useMutation } from "@tanstack/react-query";
import { createSession } from "../api/sessions";
import { CreateSessionInput } from "../schemas/session";

export function useCreateSession() {
  return useMutation({
    mutationFn: ({ coin_id, timeframe }: { coin_id: string; timeframe: string }) => {
      const parsed = CreateSessionInput.parse({ coin_id, timeframe });
      return createSession(parsed.coin_id, parsed.timeframe);
    },
  });
}
