import { atom } from "jotai";
import { atomWithStorage } from "jotai/utils";

export const selectedCoinAtom = atomWithStorage("selectedCoin", "BTC");
export const timeframeAtom = atomWithStorage("timeframe", "1h");

export const tickerAtom = atom({
  last: 0,
  change_pct: 0,
  volume: 0,
});
