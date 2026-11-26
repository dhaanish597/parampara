"use client";

import { errorMessageKey } from "@/lib/api/errors";
import { useT } from "@/lib/i18n/I18nProvider";
import type { MessageKey } from "@/lib/i18n/translate";

import { Button } from "./Button";

export function LoadingState({ label }: { label: MessageKey }) {
  const { t } = useT();
  return (
    <div role="status" aria-live="polite" className="flex flex-col gap-3 py-6">
      <span className="text-ink-soft">{t(label)}</span>
      <div className="h-20 animate-pulse rounded-xl bg-line" />
      <div className="h-20 animate-pulse rounded-xl bg-line" />
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  const { t } = useT();
  return (
    <div role="alert" className="flex flex-col gap-3 rounded-xl border border-danger bg-danger-soft p-4">
      <span className="text-danger">{t(errorMessageKey(error))}</span>
      {onRetry ? (
        <Button variant="secondary" onClick={onRetry} className="self-start">
          {t("error.retry")}
        </Button>
      ) : null}
    </div>
  );
}

export function EmptyState({ label }: { label: MessageKey }) {
  const { t } = useT();
  return <p className="rounded-xl border border-dashed border-line p-6 text-ink-soft">{t(label)}</p>;
}

export function DemoTag() {
  const { t } = useT();
  return (
    <span className="rounded bg-warn-soft px-2 py-0.5 text-xs font-medium text-warn">
      {t("skills.demoData")}
    </span>
  );
}
