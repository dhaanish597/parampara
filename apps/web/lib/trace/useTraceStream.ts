"use client";

import { useEffect, useState } from "react";

import type { TraceEvent } from "@parampara/contracts";

import { apiBase } from "../api/client";
import type { TokenSource } from "../api/client";
import { appendTrace, parseSse, shouldStopRetrying, toTraceEvent, traceQuery } from "./sse";

export type StreamStatus = "idle" | "connecting" | "live" | "offline";

export interface TraceScope {
  session_id?: string;
  compile_run_id?: string;
}

const RETRY_MS = [3000, 6000, 12000, 30000];

async function readStream(body: ReadableStream<BufferSource>, onEvent: (e: TraceEvent) => void) {
  const reader = body.pipeThrough(new TextDecoderStream()).getReader();
  let buffer = "";
  for (;;) {
    const { value, done } = await reader.read();
    if (done) return;
    const parsed = parseSse(buffer + value);
    buffer = parsed.rest;
    for (const msg of parsed.messages) {
      const event = toTraceEvent(msg);
      if (event) onEvent(event);
    }
  }
}

/** One connection attempt. Returns false when retrying cannot help (401, 403). */
async function streamOnce(
  url: string,
  getToken: TokenSource,
  signal: AbortSignal,
  on: { live: () => void; event: (e: TraceEvent) => void },
): Promise<boolean> {
  const token = await getToken();
  const res = await fetch(url, { headers: token ? { Authorization: `Bearer ${token}` } : {}, signal });
  if (shouldStopRetrying(res.status)) return false;
  if (!res.ok || !res.body) return true;
  on.live();
  await readStream(res.body as ReadableStream<BufferSource>, on.event);
  return true;
}

/** Subscribes to GET /v1/traces/stream with the bearer token; backs off between reconnects. */
export function useTraceStream(getToken: TokenSource, scope: TraceScope, enabled: boolean) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const url = `${apiBase()}/v1/traces/stream?${traceQuery({ ...scope })}`;

  useEffect(() => {
    setEvents([]); // a new user or scope never sees the previous one's events
    if (!enabled) return setStatus("idle");
    const abort = new AbortController();
    let timer: ReturnType<typeof setTimeout> | undefined;
    const connect = async (attempt: number): Promise<void> => {
      setStatus("connecting");
      const on = { live: () => setStatus("live"), event: (e: TraceEvent) => setEvents((l) => appendTrace(l, e)) };
      const retry = await streamOnce(url, getToken, abort.signal, on).catch(() => true);
      if (abort.signal.aborted) return;
      setStatus("offline");
      if (retry) timer = setTimeout(() => void connect(attempt + 1), RETRY_MS[Math.min(attempt, RETRY_MS.length - 1)]);
    };
    void connect(0);
    return () => {
      abort.abort();
      clearTimeout(timer);
    };
  }, [enabled, url, getToken]);

  return { events, status };
}
