import { AppShell, Group, NavLink } from "@mantine/core";
import { Routes, Route, Navigate, useNavigate, useLocation } from "react-router-dom";
import { Dashboard } from "./pages/Dashboard";
import { AnalysisChat } from "./pages/AnalysisChat";
import { EtlMonitor } from "./pages/EtlMonitor";

export function App() {
  const navigate = useNavigate();
  const location = useLocation();

  return (
    <AppShell header={{ height: 52 }} padding={0}>
      <AppShell.Header>
        <Group h="100%" px="md" gap="lg">
          <NavLink
            label="Dashboard"
            active={location.pathname.startsWith("/dashboard")}
            onClick={() => navigate("/dashboard")}
            style={{ width: "auto" }}
          />
          <NavLink
            label="ETL Monitor"
            active={location.pathname.startsWith("/etl")}
            onClick={() => navigate("/etl")}
            style={{ width: "auto" }}
          />
        </Group>
      </AppShell.Header>
      <AppShell.Main>
        <Routes>
          <Route path="/" element={<Navigate to="/dashboard" replace />} />
          <Route path="/dashboard" element={<Dashboard />} />
          <Route path="/analysis/:sessionId" element={<AnalysisChat />} />
          <Route path="/etl" element={<EtlMonitor />} />
        </Routes>
      </AppShell.Main>
    </AppShell>
  );
}
