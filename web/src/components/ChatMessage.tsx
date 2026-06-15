import { Paper, Text, Button, Group } from "@mantine/core";
import type { ChatMessage } from "../schemas/message";
import { MarkdownRenderer } from "./MarkdownRenderer";
import { EtlProgressCard } from "./EtlProgressCard";
import { SignalCard } from "./SignalCard";
import { pdfUrl } from "../api/sessions";

type Props = { message: ChatMessage; sessionId: string };

export function ChatMessageView({ message, sessionId }: Props) {
  const isUser = message.role === "user";

  if (message.type === "planning") {
    return null;
  }
  if (message.type === "etl_progress") {
    return <EtlProgressCard message={message} />;
  }
  if (message.type === "signal_card") {
    return <SignalCard metadata={message.metadata} content={message.content} />;
  }
  if (message.type === "report_done") {
    return (
      <Paper p="md" radius="md" bg="dark.6">
        <Text mb="sm">{message.content}</Text>
        <Group>
          <Button
            component="a"
            href={pdfUrl(sessionId)}
            target="_blank"
            rel="noreferrer"
            color="cyan"
          >
            Tải PDF
          </Button>
        </Group>
        <Text size="xs" c="dimmed" mt="sm">
          Disclaimer: Không phải lời khuyên đầu tư.
        </Text>
      </Paper>
    );
  }
  if (message.type === "report") {
    return (
      <Paper p="md" radius="md" bg="dark.6">
        <MarkdownRenderer content={message.content} />
      </Paper>
    );
  }
  if (message.type === "error") {
    return (
      <Paper p="md" radius="md" bg="red.9" c="white">
        <Text>{message.content}</Text>
      </Paper>
    );
  }

  return (
    <Paper
      p="md"
      radius="md"
      bg={isUser ? "cyan.9" : "dark.6"}
      style={{ alignSelf: isUser ? "flex-end" : "flex-start", maxWidth: "80%" }}
    >
      <Text>{message.content}</Text>
    </Paper>
  );
}
