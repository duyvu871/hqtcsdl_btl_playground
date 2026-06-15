import { useQuery } from "@tanstack/react-query";
import { getSessionMessages, sessionKeys } from "../api/sessions";
import { ChatMessageSchema } from "../schemas/message";

export function useSessionMessages(sessionId: string) {
  return useQuery({
    queryKey: sessionKeys.messages(sessionId),
    queryFn: async () => {
      const res = await getSessionMessages(sessionId);
      return res.messages.map((m) => ChatMessageSchema.parse(m));
    },
    enabled: Boolean(sessionId),
  });
}
