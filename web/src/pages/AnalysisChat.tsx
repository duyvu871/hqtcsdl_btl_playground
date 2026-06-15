import { useEffect } from "react";
import { useParams, useNavigate } from "react-router-dom";
import {
  Box,
  Stack,
  Group,
  Text,
  Badge,
  Button,
  Paper,
  ActionIcon,
  Loader,
  ThemeIcon,
} from "@mantine/core";
import {
  IconArrowLeft,
  IconFileDownload,
  IconCheck,
} from "@tabler/icons-react";
import { useAtom, useAtomValue } from "jotai";

import { chatMessagesAtom, streamingTextAtom, reportReadyAtom } from "../atoms/chat";
import { pipelineStagesAtom } from "../atoms/pipeline";
import { wsConnectedAtom } from "../atoms/ws";
import { useAnalysisWs } from "../hooks/useAnalysisWs";
import { useSessionMessages } from "../hooks/useSessionMessages";
import { mergeMessages } from "../lib/messages";
import { applyHistoryMessage } from "../lib/pipeline-state";
import { PipelineTimeline } from "../components/PipelineTimeline";
import { SignalCard } from "../components/SignalCard";
import { MarkdownRenderer } from "../components/MarkdownRenderer";
import { pdfUrl } from "../api/sessions";

// ---------------------------------------------------------------------------
// Section header helper
// ---------------------------------------------------------------------------

function SectionHead({
  num,
  label,
  color,
  extra,
}: {
  num: number;
  label: string;
  color: string;
  extra?: React.ReactNode;
}) {
  return (
    <Group gap="xs" mb="sm">
      <Box
        w={24}
        h={24}
        style={{
          borderRadius: "50%",
          background: color,
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 12,
          fontWeight: 700,
          color: "#fff",
          flexShrink: 0,
        }}
      >
        {num}
      </Box>
      <Text
        fw={700}
        size="sm"
        tt="uppercase"
        c="dimmed"
        style={{ letterSpacing: "0.05em" }}
      >
        {label}
      </Text>
      {extra}
    </Group>
  );
}

// ---------------------------------------------------------------------------
// Page
// ---------------------------------------------------------------------------

export function AnalysisChat() {
  const { sessionId = "" } = useParams<{ sessionId: string }>();
  const navigate = useNavigate();
  const history = useSessionMessages(sessionId);
  const [messages, setMessages] = useAtom(chatMessagesAtom);
  const [stageMap, setStageMap] = useAtom(pipelineStagesAtom);
  const streamingText = useAtomValue(streamingTextAtom);
  const reportReady = useAtomValue(reportReadyAtom);
  const connected = useAtomValue(wsConnectedAtom);

  useAnalysisWs(sessionId);

  useEffect(() => {
    if (history.data?.length) {
      setMessages((prev) => mergeMessages(prev, history.data!));
      // Hydrate stage map từ history etl_progress (ingest/insight mirror)
      let map = {};
      for (const msg of history.data) {
        if (msg.type === "etl_progress" || msg.type === "error") {
          map = applyHistoryMessage(map, msg);
        }
      }
      setStageMap((prev) => ({ ...map, ...prev }));
    }
  }, [history.data, setMessages, setStageMap]);

  useEffect(() => {
    return () => {
      setMessages([]);
      setStageMap({});
    };
  }, [sessionId, setMessages, setStageMap]);

  // -- derived ----------------------------------------------------------------
  const planningSteps = messages
    .filter((m) => m.type === "planning")
    .sort((a, b) => Number(a.metadata?.step ?? 0) - Number(b.metadata?.step ?? 0));

  const userMsg = messages.find((m) => m.type === "user");
  const coin =
    (userMsg?.metadata?.coin_id as string | undefined) ??
    userMsg?.content?.match(/[A-Z]{2,6}/)?.[0] ??
    "—";
  const timeframe = (userMsg?.metadata?.timeframe as string | undefined) ?? "1h";

  const signalMsgs = messages.filter((m) => m.type === "signal_card");
  const signalMsg =
    signalMsgs.find(
      (m) => String(m.metadata?.coin_id ?? "").toUpperCase() === String(coin).toUpperCase(),
    ) ?? signalMsgs.at(-1);
  const reportMsg = messages.find((m) => m.type === "report");
  const errors = messages.filter((m) => m.type === "error");

  const showPipeline = planningSteps.length > 0;
  const showSignal = !!signalMsg;
  const showReport = reportReady || !!reportMsg || !!streamingText;

  // section numbering: pipeline=1, signal=2, report=3
  const signalNum = 2;
  const reportNum = 3;

  return (
    <Box style={{ height: "calc(100vh - 52px)", display: "flex", flexDirection: "column" }}>

      {/* ── Header ─────────────────────────────────────────────────────────── */}
      <Group
        justify="space-between"
        px="md"
        py="sm"
        style={{ borderBottom: "1px solid #21262d", flexShrink: 0 }}
      >
        <Group gap="sm">
          <ActionIcon variant="subtle" size="sm" onClick={() => navigate("/dashboard")}>
            <IconArrowLeft size={16} />
          </ActionIcon>
          <Box>
            <Text fw={700}>
              Phân tích {coin} · {timeframe}
            </Text>
            <Text size="xs" c="dimmed" ff="monospace">
              {sessionId}
            </Text>
          </Box>
        </Group>

        <Group gap="sm">
          {/* Download PDF — always visible when ready, prominent */}
          {reportReady && (
            <Button
              component="a"
              href={pdfUrl(sessionId)}
              target="_blank"
              rel="noreferrer"
              leftSection={<IconFileDownload size={15} />}
              size="sm"
              color="cyan"
            >
              Tải báo cáo PDF
            </Button>
          )}
          <Badge color={connected ? "teal" : "gray"} variant="dot" size="sm">
            {connected ? "LIVE" : "Offline"}
          </Badge>
        </Group>
      </Group>

      {/* ── Scrollable content ─────────────────────────────────────────────── */}
      <Box style={{ flex: 1, overflowY: "auto" }}>
        <Stack gap="xl" p="xl" maw={860} mx="auto">

          {/* Empty / connecting */}
          {messages.length === 0 && (
            <Box ta="center" py={60} opacity={0.5}>
              <Loader size="sm" color="cyan" />
              <Text size="sm" c="dimmed" mt="sm">Đang kết nối…</Text>
            </Box>
          )}

          {/* Section 1 — Pipeline timeline (planning + execution + errors merged) */}
          {showPipeline && (
            <PipelineTimeline
              planningSteps={planningSteps}
              stageMap={stageMap}
              insightComplete={showReport}
              hasSignal={showSignal}
              animate
            />
          )}

          {/* Errors not linked to any stage (no metadata.stage) */}
          {errors
            .filter((e) => !e.metadata?.stage)
            .map((e) => (
              <Paper key={e.message_id} p="md" radius="md" bg="red.9" c="white">
                <Text size="sm">{e.content}</Text>
              </Paper>
            ))}

          {/* Section 2 — Signal */}
          {showSignal && (
            <Box>
              <SectionHead num={signalNum} label="Tín hiệu" color="#f59f00" />
              <SignalCard content={signalMsg!.content} metadata={signalMsg!.metadata} />
            </Box>
          )}

          {/* Section 3 — Report */}
          {showReport && (
            <Box>
              <SectionHead
                num={reportNum}
                label="Báo cáo phân tích"
                color="#6741d9"
                extra={
                  !reportMsg && streamingText ? (
                    <Loader size="xs" color="cyan" ml="xs" />
                  ) : reportMsg ? (
                    <ThemeIcon color="teal" variant="transparent" size="xs" ml="xs">
                      <IconCheck size={12} />
                    </ThemeIcon>
                  ) : null
                }
              />

              <Paper p="lg" radius="md" bg="dark.7" withBorder>
                <MarkdownRenderer
                  content={reportMsg?.content ?? streamingText ?? ""}
                />

                {reportReady && (
                  <Group
                    justify="space-between"
                    mt="xl"
                    pt="md"
                    style={{ borderTop: "1px solid #2c2e33" }}
                  >
                    <Text size="xs" c="dimmed">
                      Disclaimer: Không phải lời khuyên đầu tư. Chỉ mang tính chất tham khảo.
                    </Text>
                    <Button
                      component="a"
                      href={pdfUrl(sessionId)}
                      target="_blank"
                      rel="noreferrer"
                      leftSection={<IconFileDownload size={14} />}
                      size="sm"
                      color="cyan"
                      variant="light"
                    >
                      Tải PDF
                    </Button>
                  </Group>
                )}
              </Paper>
            </Box>
          )}
        </Stack>
      </Box>

      {/* ── Floating download bar (when report ready and user scrolled up) ── */}
      {reportReady && (
        <Box
          style={{
            flexShrink: 0,
            borderTop: "1px solid #21262d",
            padding: "10px 24px",
            background: "#141520",
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
          }}
        >
          <Group gap="xs">
            <ThemeIcon color="teal" variant="light" size="sm">
              <IconCheck size={12} />
            </ThemeIcon>
            <Text size="sm" fw={500}>Phân tích hoàn tất</Text>
          </Group>
          <Button
            component="a"
            href={pdfUrl(sessionId)}
            target="_blank"
            rel="noreferrer"
            leftSection={<IconFileDownload size={14} />}
            size="sm"
            color="cyan"
          >
            Tải báo cáo PDF
          </Button>
        </Box>
      )}
    </Box>
  );
}
