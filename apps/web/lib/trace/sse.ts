/** Incremental Server-Sent Events parser for /v1/traces/stream (BUILD_PLAN 12.1, 26). Pure. */
import type { TraceEvent } from "@parampara/contracts";

export interface SseMessage {
  id?: string;
  event: string;
  data: string;
}

/** Splits a text buffer into complete SSE messages and the unfinished remainder. */
export function parseSse(buffer: string): { messages: SseMessage[]; rest: string } {
  const normalised = buffer.replace(/\r\n/g, "\n");
  const blocks = normalised.split("\n\n");
  const rest = blocks.pop() ?? "";
  const messages = blocks.map(parseBlock).filter((m): m is SseMessage => m !== null);
  return { messages, rest };
}

function parseBlock(block: string): SseMessage | null {
  let id: string | undefined;
  let event = "message";
  const data: string[] = [];
  for (const line of block.split("\n")) {
    if (line.startsWith(":") || line === "") continue;
    const sep = line.indexOf(":");
    const field = sep === -1 ? line : line.slice(0, sep);
    const value = sep === -1 ? "" : line.slice(sep + 1).replace(/^ /, "");
    if (field === "id") id = value;
    else if (field === "event") event = value;
    else if (field === "data") data.push(value);
  }
  return data.length ? { id, event, data: data.join("\n") } : null;
}

/** Parses a `trace` message into a TraceEvent, or null if it is not one. */
export function toTraceEvent(message: SseMessage): TraceEvent | null {
  if (message.event !== "trace") return null;
  try {
    const parsed = JSON.parse(message.data) as TraceEvent;
    return typeof parsed.summary === "string" && typeof parsed.agent === "string" ? parsed : null;
  } catch {
    return null;
  }
}

/** Keeps the newest `limit` events, newest first, without duplicates by id. */
export function appendTrace(list: TraceEvent[], event: TraceEvent, limit = 50): TraceEvent[] {
  if (list.some((e) => e.id === event.id)) return list;
  return [event, ...list].slice(0, limit);
}
