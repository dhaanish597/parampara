// @vitest-environment jsdom
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { StepChip } from "../../components/ui/StepChip";
import { I18nProvider } from "../../lib/i18n/I18nProvider";

const title = { en: "Earth first: green wire into PE", hi: "पहले अर्थ: हरा तार PE में" };

afterEach(cleanup);

describe("StepChip", () => {
  it("shows the Hindi title by default and marks the current step", () => {
    render(
      <I18nProvider>
        <ol>
          <StepChip order={2} title={title} state="current" critical />
        </ol>
      </I18nProvider>,
    );
    const chip = screen.getByRole("listitem");
    expect(chip.textContent).toContain(title.hi);
    expect(chip.getAttribute("aria-current")).toBe("step");
    // State and criticality are announced as text, not hidden in an aria-label on the <li>.
    expect(chip.getAttribute("aria-label")).toBeNull();
    expect(chip.textContent).toContain("अभी का कदम");
    expect(chip.textContent).toContain("ज़रूरी कदम");
  });

  it("is not aria-current when pending", () => {
    render(
      <I18nProvider>
        <ol>
          <StepChip order={1} title={title} state="pending" />
        </ol>
      </I18nProvider>,
    );
    expect(screen.getByRole("listitem").getAttribute("aria-current")).toBeNull();
  });
});
