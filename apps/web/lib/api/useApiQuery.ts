"use client";

import { useCallback, useEffect, useState } from "react";

export type QueryState<T> =
  | { kind: "loading" }
  | { kind: "error"; error: unknown }
  | { kind: "ready"; data: T };

/** Runs an API call when `enabled`, exposing loading, error and data states plus reload. */
export function useApiQuery<T>(load: () => Promise<T>, enabled: boolean) {
  const [state, setState] = useState<QueryState<T>>({ kind: "loading" });
  const [attempt, setAttempt] = useState(0);
  const reload = useCallback(() => setAttempt((n) => n + 1), []);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setState({ kind: "loading" });
    load().then(
      (data) => !cancelled && setState({ kind: "ready", data }),
      (error: unknown) => !cancelled && setState({ kind: "error", error }),
    );
    return () => {
      cancelled = true;
    };
  }, [load, enabled, attempt]);

  return { state, reload };
}
