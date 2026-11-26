import { describe, expect, it } from "vitest";

import { traceQuery, shouldStopRetrying } from "../../lib/trace/sse";

describe("trace stream helpers", () => {
  it("never sends undefined scope values", () => {
    expect(traceQuery({ session_id: undefined, compile_run_id: "c1" })).toBe("compile_run_id=c1");
    expect(traceQuery({})).toBe("");
  });

  it("stops retrying on 401 and 403 only", () => {
    expect(shouldStopRetrying(401)).toBe(true);
    expect(shouldStopRetrying(403)).toBe(true);
    expect(shouldStopRetrying(503)).toBe(false);
  });
});
