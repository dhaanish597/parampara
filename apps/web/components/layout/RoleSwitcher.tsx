"use client";

/** Role switcher: native radio inputs, so keyboard and screen reader behaviour come for free. */
import { useAuth } from "@/lib/auth/AuthProvider";
import { useT } from "@/lib/i18n/I18nProvider";

export function RoleSwitcher() {
  const { t } = useT();
  const { roles, activeRole, setActiveRole } = useAuth();
  if (roles.length === 0) return null;
  return (
    <fieldset className="flex flex-col gap-2">
      <legend className="mb-2 font-semibold">{t("roles.title")}</legend>
      <div className="flex flex-wrap gap-2">
        {roles.map((role) => (
          <label
            key={role}
            className="flex min-h-touch cursor-pointer items-center rounded-xl border border-line bg-surface px-4 text-ink hover:bg-canvas has-checked:border-accent has-checked:bg-accent has-checked:text-white has-focus-visible:outline-2 has-focus-visible:outline-offset-2 has-focus-visible:outline-accent"
          >
            <input
              type="radio"
              name="active-role"
              value={role}
              checked={role === activeRole}
              onChange={() => setActiveRole(role)}
              className="sr-only"
            />
            {t(`roles.${role}`)}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
