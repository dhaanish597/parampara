/** Pure translation lookup (BUILD_PLAN 25.1). No browser APIs, so it is unit tested. */
import en from "./en.json";
import hi from "./hi.json";

export type Locale = "hi" | "en";
export type MessageKey = keyof typeof en;
export type Messages = Record<MessageKey, string>;
export type Vars = Record<string, string | number>;

export const DEFAULT_LOCALE: Locale = "hi";
export const MESSAGES: Record<Locale, Messages> = { hi, en };

/** Look up a key and fill `{name}` placeholders. Missing keys fall back to English, then the key. */
export function translate(locale: Locale, key: MessageKey, vars?: Vars): string {
  const template = MESSAGES[locale][key] ?? MESSAGES.en[key] ?? key;
  if (!vars) return template;
  return template.replace(/\{(\w+)\}/g, (match, name: string) =>
    name in vars ? String(vars[name]) : match,
  );
}

export function isLocale(value: unknown): value is Locale {
  return value === "hi" || value === "en";
}

/** Picks the current language from a contract LocalizedText, falling back to the other one. */
export function pickText(text: { en: string; hi: string }, locale: Locale): string {
  return (locale === "hi" ? text.hi : text.en) || text.en || text.hi;
}
