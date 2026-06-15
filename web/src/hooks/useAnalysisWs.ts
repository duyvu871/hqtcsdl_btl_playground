import { useEffect, useRef } from "react";
import { useSetAtom } from "jotai";
import { chatMessagesAtom, reportReadyAtom, streamingTextAtom } from "../atoms/chat";
import { pipelineStagesAtom } from "../atoms/pipeline";
import { wsConnectedAtom } from "../atoms/ws";
import { WsEventSchema } from "../schemas/ws-event";
import { wsEventToMessage, isStageEvent } from "../lib/ws-mapper";
import { appendMessage } from "../lib/messages";
import { applyWsEvent } from "../lib/pipeline-state";
import type { ChatMessage } from "../schemas/message";

function wsUrl(sessionId: string, lastId: string) {
  const proto = window.location.protocol === "https:" ? "wss" : "ws";
  const host = window.location.host;
  return `${proto}://${host}/ws/analysis/${sessionId}?last_id=${lastId}`;
}

export function useAnalysisWs(sessionId: string, lastId = "0") {
  const setMessages = useSetAtom(chatMessagesAtom);
  const setStages = useSetAtom(pipelineStagesAtom);
  const setStreaming = useSetAtom(streamingTextAtom);
  const setConnected = useSetAtom(wsConnectedAtom);
  const setReportReady = useSetAtom(reportReadyAtom);
  const streamBuf = useRef("");
  const lastEventId = useRef(lastId);

  useEffect(() => {
    if (!sessionId) return;

    let closed = false;
    streamBuf.current = "";
    setStreaming("");
    setStages({});
    lastEventId.current = lastId;

    const ws = new WebSocket(wsUrl(sessionId, lastEventId.current));

    ws.onopen = () => {
      if (!closed) setConnected(true);
    };
    ws.onclose = () => setConnected(false);
    ws.onerror = () => {
      if (!closed) setConnected(false);
    };

    ws.onmessage = ({ data }) => {
      try {
        const event = WsEventSchema.parse(JSON.parse(data as string));
        if (event.id) lastEventId.current = event.id;

        // Pipeline stage map — trực tiếp từ WS, khớp backend emit
        if (isStageEvent(event)) {
          setStages((prev) => applyWsEvent(prev, event));
        }

        if (event.event_type === "llm_token") {
          streamBuf.current += String(event.data.token ?? "");
          setStreaming(streamBuf.current);
          return;
        }

        if (event.event_type === "report_done") {
          if (streamBuf.current) {
            const reportMsg: ChatMessage = {
              message_id: `report-${event.id}`,
              session_id: sessionId,
              role: "assistant",
              type: "report",
              content: streamBuf.current,
              created_at: event.ts ?? new Date().toISOString(),
            };
            setMessages((msgs) => appendMessage(msgs, reportMsg));
            streamBuf.current = "";
            setStreaming("");
          }
          setReportReady(true);
        }

        const msg = wsEventToMessage(event, sessionId);
        if (msg) {
          setMessages((prev) => appendMessage(prev, msg));
        }
      } catch (err) {
        console.error("[WS] parse error:", err);
      }
    };

    return () => {
      closed = true;
      ws.onopen = null;
      ws.onmessage = null;
      ws.onerror = null;
      ws.onclose = null;
      if (ws.readyState === WebSocket.OPEN || ws.readyState === WebSocket.CONNECTING) {
        ws.close(1000, "unmount");
      }
    };
  }, [sessionId, lastId, setMessages, setStages, setStreaming, setConnected, setReportReady]);
}
