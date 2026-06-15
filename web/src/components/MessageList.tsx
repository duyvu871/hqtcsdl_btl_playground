import { Stack } from "@mantine/core";
import type { ChatMessage } from "../schemas/message";
import { groupForDisplay } from "../lib/messages";
import { ChatMessageView } from "./ChatMessage";
import { PlanningSteps } from "./PlanningSteps";

type Props = {
  messages: ChatMessage[];
  streamingText?: string;
  sessionId: string;
  animatePlanning?: boolean;
};

export function MessageList({ messages, streamingText, sessionId, animatePlanning }: Props) {
  const items = groupForDisplay(messages);

  return (
    <Stack gap="md" p="md" style={{ flex: 1, overflowY: "auto" }}>
      {items.map((item) =>
        item.kind === "planning_group" ? (
          <PlanningSteps
            key={`planning-${item.steps.map((s) => s.message_id).join("-")}`}
            steps={item.steps}
            animate={animatePlanning}
          />
        ) : (
          <ChatMessageView
            key={item.message.message_id}
            message={item.message}
            sessionId={sessionId}
          />
        ),
      )}
      {streamingText && (
        <ChatMessageView
          message={{
            message_id: "streaming",
            session_id: sessionId,
            role: "assistant",
            type: "report",
            content: streamingText,
            created_at: new Date().toISOString(),
          }}
          sessionId={sessionId}
        />
      )}
    </Stack>
  );
}
