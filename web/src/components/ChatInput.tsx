import { Group, TextInput, Button } from "@mantine/core";
import { useState } from "react";
import { postFollowUp } from "../api/sessions";

type Props = {
  sessionId: string;
  disabled?: boolean;
  onSent?: (content: string) => void;
};

export function ChatInput({ sessionId, disabled, onSent }: Props) {
  const [text, setText] = useState("");
  const [loading, setLoading] = useState(false);

  const send = async () => {
    const content = text.trim();
    if (!content) return;
    setLoading(true);
    try {
      await postFollowUp(sessionId, content);
      setText("");
      onSent?.(content);
    } catch (err) {
      console.error("[Chat] send failed:", err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <Group p="md" style={{ borderTop: "1px solid #21262d" }}>
      <TextInput
        style={{ flex: 1 }}
        placeholder="Hỏi thêm về phân tích…"
        value={text}
        onChange={(e) => setText(e.currentTarget.value)}
        disabled={disabled || loading}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            void send();
          }
        }}
      />
      <Button onClick={() => void send()} loading={loading} disabled={disabled}>
        Gửi
      </Button>
    </Group>
  );
}
