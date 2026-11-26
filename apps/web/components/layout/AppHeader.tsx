"use client";

import Link from "next/link";

import { useAuth } from "@/lib/auth/AuthProvider";
import { useT } from "@/lib/i18n/I18nProvider";

import { Button } from "../ui/Button";

export function AppHeader({ traceOpen, onToggleTrace }: { traceOpen: boolean; onToggleTrace: () => void }) {
  const { t, locale, setLocale } = useT();
  const { status, activeRole, signOut } = useAuth();
  return (
    <header className="sticky top-0 z-30 flex items-center gap-1 border-b border-line bg-surface/95 px-4 py-2 backdrop-blur">
      <Link href="/" className="flex min-h-touch items-center text-h2 font-semibold text-accent-strong">
        {t("app.name")}
      </Link>
      {activeRole ? (
        <span className="hidden rounded bg-accent-soft px-2 py-0.5 text-sm text-accent-strong sm:inline">
          {t("roles.active", { role: t(`roles.${activeRole}`) })}
        </span>
      ) : null}
      <div className="ml-auto flex items-center">
        {status === "signedIn" ? (
          <Button variant="ghost" size="sm" onClick={onToggleTrace} aria-expanded={traceOpen} aria-controls="trace-drawer">
            {t("header.trace")}
          </Button>
        ) : null}
        <Button
          variant="secondary"
          size="sm"
          lang={locale === "hi" ? "en" : "hi"}
          title={t("header.languageLabel")}
          onClick={() => setLocale(locale === "hi" ? "en" : "hi")}
        >
          {t("header.language")}
        </Button>
        {status === "signedIn" ? (
          <Button variant="ghost" size="sm" onClick={() => void signOut()}>
            {t("header.signOut")}
          </Button>
        ) : null}
      </div>
    </header>
  );
}
