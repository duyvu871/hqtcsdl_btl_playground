import { atom } from "jotai";
import type { ChatMessage } from "../schemas/message";

export const chatMessagesAtom = atom<ChatMessage[]>([]);
export const streamingTextAtom = atom("");
export const reportReadyAtom = atom(false);
