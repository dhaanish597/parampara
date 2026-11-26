"use client";

import { useEffect, useState } from "react";

import type { TraceEvent } from "@parampara/contracts";

import { apiBase } from "../api/client";
import type { TokenSource } from "../api/client";
import { appendTrace, parseSse, toTraceEvent } from "./sse";

export type StreamStatus = "idle" | "connecting" | "live" | "offline";

export interface TraceScope {
  session_id?: string;
  compile_run_id?: string;
}

const RETRY_MS = 3000;

async function readStream(res: Response, onEvent: (e: TraceEvent) => void): Promise<void> {
  const reader = res.body!.pipeThrough(new TextDecoderStream()).getReader();
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

/** Subscribes to GET /v1/traces/stream with the bearer token; reconnects after 3 s. */
export function useTraceStream(getToken: TokenSource, scope: TraceScope, enabled: boolean) {
  const [events, setEvents] = useState<TraceEvent[]>([]);
  const [status, setStatus] = useState<StreamStatus>("idle");
  const query = new URLSearchParams(scope as Record<string, string>).toString();

  useEffect(() => {
    if (!enabled) return setStatus("idle");
    const abort = new AbortController();
    const connect = async (): Promise<void> => {
      setStatus("connecting");
      try {
        const token = await getToken();
        const res = await fetch(`${apiBase()}/v1/traces/stream?${query}`, {
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          signal: abort.signal,
        });
        if (!res.ok || !res.body) throw new Error(`HTTP ${res.status}`);
        setStatus("live");
        await readStream(res, (e) => setEvents((list) => appendTrace(list, e)));
      } catch {
        if (abort.signal.aborted) return;
      }
      setStatus("offline");
      setTimeout(() => !abort.signal.aborted && void connect(), RETRY_MS);
    };
    void connect();
    return () => abort.abort();
  }, [enabled, query, getToken]);

  return { events, status };
}
