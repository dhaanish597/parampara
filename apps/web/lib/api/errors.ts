/** Maps API failures to i18n message keys (BUILD_PLAN 12.1 ApiError, 25.1). Pure. */
import type { ApiError } from "@parampara/contracts";

import type { MessageKey } from "../i18n/translate";

export class ApiRequestError extends Error {
  constructor(
    readonly status: number,
    readonly code: string,
    message: string,
    readonly requestId?: string,
  ) {
    super(message);
    this.name = "ApiRequestError";
  }
}

export function isApiErrorBody(body: unknown): body is ApiError {
  if (typeof body !== "object" || body === null || !("error" in body)) return false;
  const err = (body as { error: unknown }).error;
  return typeof err === "object" && err !== null && "code" in err && "message" in err;
}

export function toApiRequestError(status: number, body: unknown): ApiRequestError {
  if (isApiErrorBody(body)) {
    return new ApiRequestError(status, body.error.code, body.error.message, body.error.request_id);
  }
  return new ApiRequestError(status, "http_error", `HTTP ${status}`);
}

/** The message key a screen should show for an error thrown by the API client. */
export function errorMessageKey(error: unknown): MessageKey {
  if (!(error instanceof ApiRequestError)) return "error.network";
  if (error.status === 401) return "error.unauthorized";
  if (error.status === 403) return "error.forbidden";
  if (error.status === 404) return "error.notFound";
  return "error.generic";
}
