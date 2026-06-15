import { useQuery } from "@tanstack/react-query";
import { listSessions, sessionKeys } from "../api/sessions";
import { SessionSchema } from "../schemas/session";

export function useSessions(limit = 20) {
  return useQuery({
    queryKey: sessionKeys.all,
    queryFn: async () => {
      const res = await listSessions(limit);
      return res.sessions.map((s) => SessionSchema.parse(s));
    },
    refetchInterval: 30_000,
  });
}
