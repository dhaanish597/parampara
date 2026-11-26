import { describe, expect, it } from "vitest";

import { ApiRequestError } from "../../lib/api/errors";
import { restoreOutcome } from "../../lib/auth/roles";

describe("restoreOutcome", () => {
  it("signs out a stale session the API rejects", () => {
    expect(restoreOutcome(new ApiRequestError(401, "invalid_token", "x"))).toBe("signOut");
  });

  it("keeps the session and offers retry on network and server errors", () => {
    expect(restoreOutcome(new TypeError("Failed to fetch"))).toBe("retry");
    expect(restoreOutcome(new ApiRequestError(503, "db_unavailable", "x"))).toBe("retry");
  });
});
