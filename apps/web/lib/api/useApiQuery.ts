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
    // Disabled (signed out, or switching user): never keep the previous user's data.
    setState({ kind: "loading" });
    if (!enabled) return;
    let cancelled = false;
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
