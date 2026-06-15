import { atom } from "jotai";
import type { StageMap } from "../lib/pipeline-state";

export const pipelineStagesAtom = atom<StageMap>({});
