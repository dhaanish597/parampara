"use client";

/** Trace drawer (BUILD_PLAN 25.1, 26): right drawer on desktop, bottom sheet on mobile. */
import { useEffect } from "react";

import type { TraceEvent } from "@parampara/contracts";

import { useAuth } from "@/lib/auth/AuthProvider";
import { useT } from "@/lib/i18n/I18nProvider";
import { useTraceStream } from "@/lib/trace/useTraceStream";
import type { StreamStatus, TraceScope } from "@/lib/trace/useTraceStream";

import { Button } from "../ui/Button";

const STATUS_KEY = {
  idle: "trace.offline",
  connecting: "trace.connecting",
  live: "trace.live",
  offline: "trace.offline",
} as const satisfies Record<StreamStatus, string>;

function TraceRow({ event }: { event: TraceEvent }) {
  const { t } = useT();
  const seconds =
    event.latency_ms != null ? ` · ${t("trace.seconds", { value: (event.latency_ms / 1000).toFixed(1) })}` : "";
  return (
    <li className="border-b border-line py-2 last:border-0">
      <div className="text-xs uppercase tracking-wide text-ink-soft">
        {event.agent} · {event.kind}
        {seconds}
      </div>
      <div lang="en" className="text-sm">
        {event.summary}
      </div>
    </li>
  );
}

export function TraceDrawer({ open, onClose, scope = {} }: {
  open: boolean;
  onClose: () => void;
  scope?: TraceScope;
}) {
  const { t } = useT();
  const { getToken, status: authStatus } = useAuth();
  const { events, status } = useTraceStream(getToken, scope, open && authStatus === "signedIn");
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, onClose]);
  if (!open) return null;
  return (
    <aside
      id="trace-drawer"
      aria-label={t("trace.title")}
      className="fixed inset-x-0 bottom-0 z-40 flex max-h-[60vh] flex-col rounded-t-2xl border border-line bg-surface shadow-xl md:inset-y-0 md:right-0 md:left-auto md:max-h-none md:w-96 md:rounded-none"
    >
      <header className="flex items-center gap-3 border-b border-line px-4 py-2">
        <h2 className="text-h2 font-semibold">{t("trace.title")}</h2>
        <span role="status" className={status === "live" ? "text-ok text-sm" : "text-ink-soft text-sm"}>
          {t(STATUS_KEY[status])}
        </span>
        <Button variant="ghost" onClick={onClose} className="ml-auto">
          {t("trace.close")}
        </Button>
      </header>
      <ol className="overflow-y-auto px-4">
        {events.length === 0 ? <li className="py-4 text-ink-soft">{t("trace.empty")}</li> : null}
        {events.map((event) => (
          <TraceRow key={event.id} event={event} />
        ))}
      </ol>
    </aside>
  );
}
