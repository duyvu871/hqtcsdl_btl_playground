import { useEffect, useRef, useState } from "react";
import { Paper, Text, Box, Group, Stack } from "@mantine/core";
import type { ChatMessage } from "../schemas/message";
import { messageDedupeKey } from "../lib/messages";

type Props = {
  steps: ChatMessage[];
  animate?: boolean;
};

export function PlanningSteps({ steps, animate = true }: Props) {
  const [visibleCount, setVisibleCount] = useState(animate ? 0 : steps.length);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  useEffect(() => {
    if (!animate) {
      setVisibleCount(steps.length);
      return;
    }
    setVisibleCount(0);
    if (timerRef.current) clearInterval(timerRef.current);

    let n = 0;
    timerRef.current = setInterval(() => {
      n += 1;
      setVisibleCount(n);
      if (n >= steps.length && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 350);

    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
    };
  }, [steps.length, animate]);

  const shown = steps.slice(0, visibleCount);
  const planning = visibleCount < steps.length;

  return (
    <Paper p="lg" radius="md" bg="dark.7" withBorder>
      <Group gap="xs" mb="md">
        <Box
          w={24}
          h={24}
          style={{
            borderRadius: "50%",
            background: "#0ca678",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 12,
            fontWeight: 700,
            color: "#fff",
            flexShrink: 0,
          }}
        >
          1
        </Box>
        <Text fw={700} size="sm" tt="uppercase" c="dimmed" style={{ letterSpacing: "0.05em" }}>
          Kế hoạch phân tích
        </Text>
        {planning && (
          <Text size="xs" c="cyan" ml="auto">
            Đang lập kế hoạch…
          </Text>
        )}
      </Group>

      <Stack gap={6}>
        {shown.map((step, i) => (
          <Group
            key={messageDedupeKey(step)}
            gap="xs"
            style={{
              opacity: 1,
              animation: animate ? "fadeSlideIn 0.3s ease" : undefined,
            }}
          >
            <Text size="xs" c="dimmed" w={18} ta="right" ff="monospace">
              {i + 1}.
            </Text>
            <Text size="sm" style={{ flex: 1 }}>
              {step.content}
            </Text>
          </Group>
        ))}

        {planning && (
          <Group gap="xs" opacity={0.5}>
            <Text size="xs" c="dimmed" w={18} ta="right" ff="monospace">
              {shown.length + 1}.
            </Text>
            <Text size="sm" c="dimmed">
              ···
            </Text>
          </Group>
        )}
      </Stack>
    </Paper>
  );
}
