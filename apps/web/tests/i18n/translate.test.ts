import { describe, expect, it } from "vitest";

import en from "../../lib/i18n/en.json";
import hi from "../../lib/i18n/hi.json";
import { pickText, translate } from "../../lib/i18n/translate";

const DEVANAGARI = /[ऀ-ॿ]/;
const placeholders = (s: string) => [...s.matchAll(/\{(\w+)\}/g)].map((m) => m[1]).sort();
// Values that are intentionally not Devanagari in hi.json.
const HI_EXCEPTIONS = new Set(["header.language"]);

describe("message files", () => {
  it("hi.json and en.json have exactly the same keys", () => {
    expect(Object.keys(hi).sort()).toEqual(Object.keys(en).sort());
  });

  it("every Hindi string is in Devanagari", () => {
    const notHindi = Object.entries(hi).filter(
      ([key, value]) => !HI_EXCEPTIONS.has(key) && !DEVANAGARI.test(value),
    );
    expect(notHindi).toEqual([]);
  });

  it("placeholders match between languages", () => {
    for (const key of Object.keys(en) as (keyof typeof en)[]) {
      expect(placeholders(hi[key]), key).toEqual(placeholders(en[key]));
    }
  });
});

describe("translate", () => {
  it("fills placeholders and leaves unknown ones visible", () => {
    expect(translate("en", "skills.version", { version: 2 })).toBe("Version 2");
    expect(translate("hi", "skills.version", { version: 2 })).toBe("संस्करण 2");
    expect(translate("en", "skills.version")).toBe("Version {version}");
  });

  it("picks LocalizedText by locale and falls back when one side is empty", () => {
    expect(pickText({ en: "Earth first", hi: "पहले अर्थ" }, "hi")).toBe("पहले अर्थ");
    expect(pickText({ en: "Earth first", hi: "" }, "hi")).toBe("Earth first");
  });
});
