import { NavLink, Stack, Text, Badge } from "@mantine/core";
import { useNavigate } from "react-router-dom";
import type { Session } from "../schemas/session";

type Props = { sessions: Session[]; loading?: boolean };

export function SessionSidebar({ sessions, loading }: Props) {
  const navigate = useNavigate();

  return (
    <Stack gap="xs" p="md" style={{ width: 260, borderRight: "1px solid #21262d", minHeight: "100%" }}>
      <Text fw={600} size="sm" c="dimmed">LỊCH SỬ PHÂN TÍCH</Text>
      {loading && <Text size="sm" c="dimmed">Đang tải…</Text>}
      {sessions.map((s) => (
        <NavLink
          key={s.session_id}
          label={`${s.coin_id} · ${s.timeframe}`}
          description={s.created_at?.slice(0, 16) ?? s.session_id.slice(0, 8)}
          rightSection={
            <Badge size="xs" variant="outline">{s.status ?? "—"}</Badge>
          }
          onClick={() => navigate(`/analysis/${s.session_id}`)}
        />
      ))}
      {!loading && sessions.length === 0 && (
        <Text size="sm" c="dimmed">Chưa có session nào.</Text>
      )}
    </Stack>
  );
}
