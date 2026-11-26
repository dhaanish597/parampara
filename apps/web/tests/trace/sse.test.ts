import { describe, expect, it } from "vitest";

import { appendTrace, parseSse, toTraceEvent } from "../../lib/trace/sse";

const event = (id: number) => ({
  id,
  scope: { session_id: "s" },
  agent: "verifier",
  kind: "verdict" as const,
  summary: `Verifier: step s${id} pass`,
  created_at: "2026-11-26T00:00:00Z",
});

describe("parseSse", () => {
  it("returns complete messages and keeps a partial one for the next chunk", () => {
    const first = parseSse(`id: 1\nevent: trace\ndata: ${JSON.stringify(event(1))}\n\nid: 2\nev`);
    expect(first.messages).toHaveLength(1);
    expect(first.messages[0]?.id).toBe("1");
    const second = parseSse(`${first.rest}ent: trace\ndata: ${JSON.stringify(event(2))}\n\n`);
    expect(second.messages.map((m) => m.id)).toEqual(["2"]);
    expect(second.rest).toBe("");
  });

  it("ignores comments and joins multi-line data", () => {
    const { messages } = parseSse(": keepalive\n\ndata: a\ndata: b\n\n");
    expect(messages).toEqual([{ id: undefined, event: "message", data: "a\nb" }]);
  });

  it("handles CRLF line endings", () => {
    expect(parseSse("event: trace\r\ndata: x\r\n\r\n").messages).toHaveLength(1);
  });
});

describe("toTraceEvent and appendTrace", () => {
  it("accepts only trace events with valid JSON", () => {
    expect(toTraceEvent({ event: "trace", data: JSON.stringify(event(1)) })?.id).toBe(1);
    expect(toTraceEvent({ event: "trace", data: "{oops" })).toBeNull();
    expect(toTraceEvent({ event: "ping", data: "{}" })).toBeNull();
  });

  it("puts the newest first, drops duplicates and keeps the limit", () => {
    let list = appendTrace([], event(1));
    list = appendTrace(list, event(2));
    list = appendTrace(list, event(2));
    expect(list.map((e) => e.id)).toEqual([2, 1]);
    expect(appendTrace(list, event(3), 2).map((e) => e.id)).toEqual([3, 2]);
  });
});
