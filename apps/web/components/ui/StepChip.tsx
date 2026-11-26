"use client";

/**
 * Exemplar component (BUILD_PLAN 31.4): typed props from contracts, Tailwind tokens only,
 * every string through useT(), accessible name and state, 48 px touch target.
 */
import type { LocalizedText } from "@parampara/contracts";

import { pickText } from "@/lib/i18n/translate";
import { useT } from "@/lib/i18n/I18nProvider";

export type StepChipState = "pending" | "current" | "done" | "failed";

export interface StepChipProps {
  order: number;
  title: LocalizedText;
  state: StepChipState;
  critical?: boolean;
}

const STATE_CLASSES: Record<StepChipState, string> = {
  pending: "border-line bg-surface text-ink-soft",
  current: "border-accent bg-accent-soft text-accent-strong ring-2 ring-accent",
  done: "border-ok bg-ok-soft text-ok",
  failed: "border-danger bg-danger-soft text-danger",
};

const STATE_ICONS: Record<StepChipState, string> = {
  pending: "○",
  current: "●",
  done: "✓",
  failed: "!",
};

export function StepChip({ order, title, state, critical = false }: StepChipProps) {
  const { t, locale } = useT();
  return (
    <li
      className={`flex min-h-touch items-center gap-2 rounded-xl border px-3 py-2 ${STATE_CLASSES[state]}`}
      aria-current={state === "current" ? "step" : undefined}
    >
      <span aria-hidden="true" className="w-5 text-center font-semibold">
        {STATE_ICONS[state]}
      </span>
      <span className="font-medium">{order}</span>
      <span className="min-w-0 break-words">{pickText(title, locale)}</span>
      <span className="sr-only">{t(`step.state.${state}`)}</span>
      {critical ? (
        <span className="ml-auto shrink-0 whitespace-nowrap rounded bg-warn-soft px-1.5 text-xs text-warn">
          {t("step.critical")}
        </span>
      ) : null}
    </li>
  );
}
