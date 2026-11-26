import { describe, expect, it } from "vitest";

import { ApiRequestError, errorMessageKey, toApiRequestError } from "../../lib/api/errors";

describe("API errors", () => {
  it("reads the ApiError envelope", () => {
    const err = toApiRequestError(403, {
      error: { code: "forbidden", message: "Requires one of roles", request_id: "r1" },
    });
    expect(err).toMatchObject({ status: 403, code: "forbidden", requestId: "r1" });
  });

  it("falls back to http_error for bodies that are not ApiError", () => {
    expect(toApiRequestError(500, { detail: "x" }).code).toBe("http_error");
  });

  it("maps statuses to message keys; non-API failures are network errors", () => {
    expect(errorMessageKey(new ApiRequestError(401, "x", "x"))).toBe("error.unauthorized");
    expect(errorMessageKey(new ApiRequestError(403, "x", "x"))).toBe("error.forbidden");
    expect(errorMessageKey(new ApiRequestError(404, "x", "x"))).toBe("error.notFound");
    expect(errorMessageKey(new ApiRequestError(500, "x", "x"))).toBe("error.generic");
    expect(errorMessageKey(new TypeError("Failed to fetch"))).toBe("error.network");
  });
});
