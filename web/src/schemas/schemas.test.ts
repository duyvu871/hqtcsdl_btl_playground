import { describe, expect, it } from "vitest";
import { ZodError } from "zod";
import { ChatMessageSchema } from "./message";
import { CreateSessionInput } from "./session";

describe("T9-01 ChatMessageSchema", () => {
  it("parses valid message", () => {
    const msg = ChatMessageSchema.parse({
      message_id: "msg-001",
      session_id: "sess-abc",
      role: "assistant",
      type: "planning",
      content: "Step 1",
      created_at: "2026-06-13T10:00:00Z",
    });
    expect(msg.type).toBe("planning");
  });

  it("throws on invalid type", () => {
    expect(() =>
      ChatMessageSchema.parse({
        message_id: "x",
        session_id: "y",
        role: "assistant",
        type: "invalid",
        content: "",
        created_at: "2026-06-13T10:00:00Z",
      }),
    ).toThrow(ZodError);
  });
});

describe("T9-02 CreateSessionInput", () => {
  it("rejects invalid coin", () => {
    expect(() =>
      CreateSessionInput.parse({ coin_id: "INVALID", timeframe: "1h" }),
    ).toThrow(ZodError);
  });

  it("accepts BTC 1h", () => {
    const v = CreateSessionInput.parse({ coin_id: "BTC", timeframe: "1h" });
    expect(v.coin_id).toBe("BTC");
  });
});
