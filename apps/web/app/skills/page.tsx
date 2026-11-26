"use client";

/**
 * Exemplar page (BUILD_PLAN 31.4): data through the typed API client and useApiQuery,
 * every string through useT(), explicit loading, error, empty and signed-out states.
 */
import { useCallback } from "react";

import { StepChip } from "@/components/ui/StepChip";
import { EmptyState, ErrorState, LoadingState } from "@/components/ui/States";
import { listSkillVersions } from "@/lib/api/endpoints";
import type { SkillVersionSummary } from "@/lib/api/types";
import { useApiQuery } from "@/lib/api/useApiQuery";
import { useAuth } from "@/lib/auth/AuthProvider";
import { primaryOrgId } from "@/lib/auth/roles";
import { pickText } from "@/lib/i18n/translate";
import { useT } from "@/lib/i18n/I18nProvider";

function SkillCard({ skill }: { skill: SkillVersionSummary }) {
  const { t, locale } = useT();
  const steps = [...skill.graph.steps].sort((a, b) => a.order - b.order);
  return (
    <article className="flex flex-col gap-3 rounded-2xl border border-line bg-surface p-4">
      <header className="flex flex-wrap items-baseline gap-2">
        <h2 className="text-h2 font-semibold">{pickText(skill.graph.title, locale)}</h2>
        <span className="rounded bg-ok-soft px-2 py-0.5 text-sm text-ok">
          {t(`skills.status.${skill.status}`)}
        </span>
        <span className="text-sm text-ink-soft">
          {t("skills.version", { version: skill.version })} · {t("skills.steps", { count: steps.length })}
        </span>
      </header>
      <p className="text-ink-soft">{pickText(skill.graph.summary, locale)}</p>
      <ol className="flex flex-col gap-2">
        {steps.map((step) => (
          <StepChip key={step.id} order={step.order} title={step.title} state="pending" critical={step.critical} />
        ))}
      </ol>
    </article>
  );
}

export default function SkillsPage() {
  const { t } = useT();
  const { api, me, status, error: authError, retry } = useAuth();
  const orgId = primaryOrgId(me);
  const load = useCallback(() => listSkillVersions(api, orgId ?? ""), [api, orgId]);
  const signedIn = status === "signedIn";
  const { state, reload } = useApiQuery(load, signedIn && orgId !== null);

  return (
    <section className="flex flex-col gap-4">
      <h1 className="text-h1 font-semibold">{t("skills.title")}</h1>
      <p className="text-ink-soft">{t("skills.subtitle")}</p>
      {status === "signedOut" || status === "unavailable" ? <EmptyState label="skills.signInFirst" /> : null}
      {status === "error" ? <ErrorState error={authError} onRetry={retry} /> : null}
      {signedIn && orgId === null ? <EmptyState label="skills.noOrg" /> : null}
      {signedIn && orgId !== null && state.kind === "loading" ? <LoadingState label="skills.loading" /> : null}
      {signedIn && state.kind === "error" ? <ErrorState error={state.error} onRetry={reload} /> : null}
      {signedIn && state.kind === "ready" && state.data.length === 0 ? <EmptyState label="skills.empty" /> : null}
      {signedIn && state.kind === "ready" ? state.data.map((skill) => <SkillCard key={skill.id} skill={skill} />) : null}
    </section>
  );
}
