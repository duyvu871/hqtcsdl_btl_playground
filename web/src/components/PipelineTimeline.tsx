/**
 * PipelineTimeline — hiển thị planning + stage progress từ pipelineStagesAtom.
 */
import { useEffect, useRef, useState } from "react";
import {
  Box,
  Group,
  Text,
  Stack,
  Badge,
  ThemeIcon,
} from "@mantine/core";
import {
  IconCheck,
  IconX,
  IconLoader2,
  IconClock,
  IconDatabase,
  IconFilter,
  IconBrain,
  IconChartBar,
  IconTrendingUp,
  IconSparkles,
} from "@tabler/icons-react";
import type { ChatMessage } from "../schemas/message";
import {
  buildTimelineRows,
  type StageMap,
  type TimelineRow,
  type RowStatus,
} from "../lib/pipeline-state";

const STAGE_ICON: Record<string, React.ReactNode> = {
  ingest: <IconDatabase size={14} />,
  filter: <IconFilter size={14} />,
  ner: <IconBrain size={14} />,
  sentiment: <IconBrain size={14} />,
  influence: <IconChartBar size={14} />,
  scoring: <IconTrendingUp size={14} />,
  insight: <IconSparkles size={14} />,
};

function AnimBar({ value, status }: { value: number; status: RowStatus }) {
  const [displayed, setDisplayed] = useState(0);
  const raf = useRef<number | null>(null);

  useEffect(() => {
    const target = value;
    const start = displayed;
    const duration = 700;
    const startTime = performance.now();

    const tick = (now: number) => {
      const elapsed = now - startTime;
      const progress = Math.min(elapsed / duration, 1);
      const eased = 1 - Math.pow(1 - progress, 3);
      setDisplayed(Math.round(start + (target - start) * eased));
      if (progress < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    return () => {
      if (raf.current) cancelAnimationFrame(raf.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value]);

  const fillColor =
    status === "done" ? "#12b886"
    : status === "failed" ? "#fa5252"
    : status === "running" ? "#15aabf"
    : "#2c2e33";

  return (
    <Box style={{ background: "#1e2030", borderRadius: 6, height: 6, overflow: "hidden", position: "relative" }}>
      <Box style={{ background: fillColor, height: "100%", width: `${displayed}%`, borderRadius: 6 }} />
      {status === "running" && (
        <Box
          style={{
            position: "absolute", top: 0, left: 0, height: "100%", width: "40%",
            background: "linear-gradient(90deg, transparent 0%, rgba(255,255,255,0.15) 50%, transparent 100%)",
            animation: "shimmer 1.5s infinite",
          }}
        />
      )}
    </Box>
  );
}

function StatusIcon({ status }: { status: RowStatus }) {
  if (status === "done")
    return <ThemeIcon color="teal" variant="light" size={28} radius="xl"><IconCheck size={14} /></ThemeIcon>;
  if (status === "failed")
    return <ThemeIcon color="red" variant="light" size={28} radius="xl"><IconX size={14} /></ThemeIcon>;
  if (status === "running")
    return (
      <ThemeIcon color="cyan" variant="light" size={28} radius="xl">
        <IconLoader2 size={14} style={{ animation: "spin 1s linear infinite" }} />
      </ThemeIcon>
    );
  return <ThemeIcon color="dark" variant="light" size={28} radius="xl"><IconClock size={14} /></ThemeIcon>;
}

function TimelineRowView({ row, visible }: { row: TimelineRow; visible: boolean }) {
  const badgeColor =
    row.status === "done" ? "teal"
    : row.status === "failed" ? "red"
    : row.status === "running" ? "cyan"
    : "dark";

  const badgeLabel =
    row.status === "done" ? "hoàn thành"
    : row.status === "failed" ? "lỗi"
    : row.status === "running" ? "đang chạy"
    : "chờ";

  return (
    <Box
      style={{
        opacity: visible ? 1 : 0,
        transform: visible ? "translateY(0)" : "translateY(8px)",
        transition: "opacity 0.35s ease, transform 0.35s ease",
      }}
    >
      <Group gap="md" align="flex-start" wrap="nowrap">
        <Box style={{ flexShrink: 0, paddingTop: 2 }}>
          <StatusIcon status={row.status} />
        </Box>
        <Box style={{ flex: 1, minWidth: 0 }}>
          <Group gap="xs" mb={4} wrap="nowrap">
            <Box style={{ color: "#a0aec0" }}>{STAGE_ICON[row.stage] ?? <IconDatabase size={14} />}</Box>
            <Text size="sm" fw={600} c={row.status === "pending" ? "dimmed" : "white"}>
              {row.stepNum}. {row.label}
            </Text>
            <Badge size="xs" variant="light" color={badgeColor} ml="auto">{badgeLabel}</Badge>
          </Group>

          {row.description && (
            <Text size="xs" c="dimmed" mb={6} style={{ lineHeight: 1.5 }}>{row.description}</Text>
          )}

          <Group gap="xs" align="center">
            <Box style={{ flex: 1 }}><AnimBar value={row.pct} status={row.status} /></Box>
            <Text size="xs" c="dimmed" miw={32} ta="right" ff="monospace">{row.pct}%</Text>
          </Group>

          {row.detail && <Text size="xs" c="teal" mt={4}>✓ {row.detail}</Text>}

          {row.errorMsg && (
            <Box mt={6} px="sm" py={6} style={{ background: "rgba(250,82,82,0.12)", border: "1px solid rgba(250,82,82,0.3)", borderRadius: 6 }}>
              <Text size="xs" c="red.4" ff="monospace" style={{ wordBreak: "break-all" }}>✗ {row.errorMsg}</Text>
            </Box>
          )}
        </Box>
      </Group>
    </Box>
  );
}

type Props = {
  planningSteps: ChatMessage[];
  stageMap: StageMap;
  insightComplete?: boolean;
  hasSignal?: boolean;
  animate?: boolean;
};

export function PipelineTimeline({
  planningSteps,
  stageMap,
  insightComplete = false,
  hasSignal = false,
  animate = true,
}: Props) {
  const rows = buildTimelineRows(planningSteps, stageMap, { insightComplete, hasSignal });

  const [visibleCount, setVisibleCount] = useState(animate ? 0 : rows.length);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const prevLenRef = useRef(0);

  useEffect(() => {
    if (rows.length === 0) return;
    if (!animate) { setVisibleCount(rows.length); return; }
    if (rows.length <= prevLenRef.current) {
      setVisibleCount((c) => Math.max(c, rows.length));
      return;
    }
    prevLenRef.current = rows.length;
    if (timerRef.current) clearInterval(timerRef.current);
    let n = visibleCount;
    timerRef.current = setInterval(() => {
      n += 1;
      setVisibleCount(n);
      if (n >= rows.length && timerRef.current) {
        clearInterval(timerRef.current);
        timerRef.current = null;
      }
    }, 350);
    return () => { if (timerRef.current) clearInterval(timerRef.current); };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [rows.length, animate]);

  if (rows.length === 0) return null;

  const doneCount = rows.filter((r) => r.status === "done").length;
  const runningRow = rows.find((r) => r.status === "running");

  return (
    <Box>
      <Group gap="xs" mb="md">
        <Box w={24} h={24} style={{ borderRadius: "50%", background: "#0ca678", display: "flex", alignItems: "center", justifyContent: "center", fontSize: 12, fontWeight: 700, color: "#fff", flexShrink: 0 }}>1</Box>
        <Text fw={700} size="sm" tt="uppercase" c="dimmed" style={{ letterSpacing: "0.05em" }}>Kế hoạch &amp; Thực thi</Text>
        <Text size="xs" c="dimmed" ml="auto">
          {doneCount}/{rows.length} bước
          {runningRow && <Text span c="cyan" ml={4}>· đang: {runningRow.label}</Text>}
        </Text>
      </Group>

      <Box p="md" style={{ background: "#141520", borderRadius: 12, border: "1px solid #21262d" }}>
        <Stack gap="lg">
          {rows.map((row, i) => (
            <TimelineRowView key={`${row.stage}-${row.stepNum}`} row={row} visible={i < visibleCount} />
          ))}
        </Stack>
      </Box>
    </Box>
  );
}
