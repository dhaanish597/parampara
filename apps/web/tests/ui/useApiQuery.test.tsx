// @vitest-environment jsdom
import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { useApiQuery } from "../../lib/api/useApiQuery";

afterEach(cleanup);

describe("useApiQuery", () => {
  it("drops the previous data when the query is disabled (sign-out)", async () => {
    const load = () => Promise.resolve(["previous user's skill"]);
    const { result, rerender } = renderHook(({ enabled }) => useApiQuery(load, enabled), {
      initialProps: { enabled: true },
    });
    await act(async () => {});
    expect(result.current.state.kind).toBe("ready");

    rerender({ enabled: false });

    expect(result.current.state.kind).toBe("loading");
  });
});
