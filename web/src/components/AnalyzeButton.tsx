import { Button } from "@mantine/core";
import { useNavigate } from "react-router-dom";
import { useAtomValue } from "jotai";
import { selectedCoinAtom, timeframeAtom } from "../atoms/market";
import { useCreateSession } from "../hooks/useCreateSession";

export function AnalyzeButton() {
  const coin = useAtomValue(selectedCoinAtom);
  const timeframe = useAtomValue(timeframeAtom);
  const navigate = useNavigate();
  const create = useCreateSession();

  const handleClick = () => {
    create.mutate(
      { coin_id: coin, timeframe },
      { onSuccess: (res) => navigate(`/analysis/${res.session_id}`) },
    );
  };

  return (
    <Button
      size="md"
      color="cyan"
      loading={create.isPending}
      onClick={handleClick}
    >
      Phân tích
    </Button>
  );
}
