"use client";

import Link from "next/link";

import { RoleSwitcher } from "@/components/layout/RoleSwitcher";
import { Button } from "@/components/ui/Button";
import { ErrorState } from "@/components/ui/States";
import { useAuth } from "@/lib/auth/AuthProvider";
import { useT } from "@/lib/i18n/I18nProvider";

function JudgeEntry() {
  const { t } = useT();
  const { status, tryAsJudge, error, retry } = useAuth();
  if (status === "unavailable") return <p className="text-danger">{t("error.authUnavailable")}</p>;
  if (status === "error") return <ErrorState error={error} onRetry={retry} />;
  return (
    <div className="flex flex-col gap-3">
      <div className="fixed inset-x-0 bottom-0 z-20 border-t border-line bg-surface p-4 sm:static sm:border-0 sm:bg-transparent sm:p-0">
        <Button className="w-full sm:w-auto" disabled={status === "signingIn" || status === "loading"} onClick={() => void tryAsJudge()}>
          {status === "signingIn" ? t("landing.signingIn") : t("landing.tryJudge")}
        </Button>
      </div>
      <p className="text-sm text-ink-soft">{t("landing.judgeNote")}</p>
      {error ? <ErrorState error={error} /> : null}
    </div>
  );
}

function SignedIn() {
  const { t } = useT();
  const { me } = useAuth();
  return (
    <div className="flex flex-col gap-5">
      <p className="text-ink-soft">{t("landing.loggedInAs", { name: me?.profile.display_name ?? "" })}</p>
      <RoleSwitcher />
      <Link href="/skills" className="inline-flex min-h-touch items-center self-start rounded-xl bg-accent px-4 font-medium text-white">
        {t("landing.openSkills")}
      </Link>
    </div>
  );
}

export default function LandingPage() {
  const { t } = useT();
  const { status } = useAuth();
  return (
    <section className="flex flex-col gap-6">
      <h1 className="text-h1 font-semibold">{t("app.name")}</h1>
      <p className="text-lg">{t("app.tagline")}</p>
      {status === "signedIn" ? <SignedIn /> : <JudgeEntry />}
      <p className="text-sm text-ink-soft">
        {t("landing.verifySample")} · {t("landing.comingSoon")}
      </p>
      <p className="text-sm font-medium text-warn">{t("safety.neverPowered")}</p>
    </section>
  );
}
