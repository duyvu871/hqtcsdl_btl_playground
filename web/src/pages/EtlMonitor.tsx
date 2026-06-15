import { Button, Group, Paper, Stack, Table, Text, Title } from "@mantine/core";
import { usePipelineJobs, useRunPipeline } from "../hooks/usePipelineJobs";

type Job = {
  job_id?: string;
  session_id?: string;
  status?: string;
  coin_id?: string;
  timeframe?: string;
  started_at?: string;
};

export function EtlMonitor() {
  const jobs = usePipelineJobs();
  const run = useRunPipeline();

  const rows = (jobs.data?.jobs ?? []) as Job[];

  return (
    <Stack p="md" gap="md">
      <Group justify="space-between">
        <Title order={3}>ETL Monitor</Title>
        <Button
          color="cyan"
          loading={run.isPending}
          onClick={() => run.mutate({ coin_id: "BTC", timeframe: "1h" })}
        >
          Run All
        </Button>
      </Group>

      <Paper p="md" radius="md" bg="dark.6">
        <Text size="sm" c="dimmed" mb="sm">
          WebSocket /ws/pipeline — live job events (kết nối khi có job running)
        </Text>
        <Table striped highlightOnHover>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Job ID</Table.Th>
              <Table.Th>Coin</Table.Th>
              <Table.Th>TF</Table.Th>
              <Table.Th>Status</Table.Th>
              <Table.Th>Started</Table.Th>
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {rows.map((j) => (
              <Table.Tr key={j.job_id}>
                <Table.Td>{j.job_id}</Table.Td>
                <Table.Td>{j.coin_id}</Table.Td>
                <Table.Td>{j.timeframe}</Table.Td>
                <Table.Td>{j.status}</Table.Td>
                <Table.Td>{j.started_at?.slice(0, 19) ?? "—"}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {!rows.length && <Text c="dimmed" ta="center" py="lg">Chưa có job nào.</Text>}
      </Paper>
    </Stack>
  );
}
