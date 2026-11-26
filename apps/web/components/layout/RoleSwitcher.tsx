"use client";

import { useAuth } from "@/lib/auth/AuthProvider";
import { useT } from "@/lib/i18n/I18nProvider";

export function RoleSwitcher() {
  const { t } = useT();
  const { roles, activeRole, setActiveRole } = useAuth();
  if (roles.length === 0) return null;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 font-semibold">{t("roles.title")}</legend>
      <div role="radiogroup" className="flex flex-wrap gap-2">
        {roles.map((role) => (
          <button
            key={role}
            type="button"
            role="radio"
            aria-checked={role === activeRole}
            onClick={() => setActiveRole(role)}
            className={`min-h-touch rounded-xl border px-4 ${
              role === activeRole
                ? "border-accent bg-accent text-white"
                : "border-line bg-surface text-ink hover:bg-canvas"
            }`}
          >
            {t(`roles.${role}`)}
          </button>
        ))}
      </div>
    </fieldset>
  );
}
