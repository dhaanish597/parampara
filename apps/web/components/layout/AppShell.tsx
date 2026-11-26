"use client";

import { useCallback, useState } from "react";
import type { ReactNode } from "react";

import { AuthProvider } from "@/lib/auth/AuthProvider";
import { I18nProvider } from "@/lib/i18n/I18nProvider";

import { TraceDrawer } from "../trace/TraceDrawer";
import { AppHeader } from "./AppHeader";

export function AppShell({ children }: { children: ReactNode }) {
  const [traceOpen, setTraceOpen] = useState(false);
  const closeTrace = useCallback(() => setTraceOpen(false), []);
  return (
    <I18nProvider>
      <AuthProvider>
        <AppHeader traceOpen={traceOpen} onToggleTrace={() => setTraceOpen((open) => !open)} />
        <main className="mx-auto w-full max-w-3xl px-4 pt-6 pb-28">{children}</main>
        <TraceDrawer open={traceOpen} onClose={closeTrace} />
      </AuthProvider>
    </I18nProvider>
  );
}
