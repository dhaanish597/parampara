/** Typed API client (BUILD_PLAN 12, T-012 AC3): generated OpenAPI paths + bearer auth. */
import createClient from "openapi-fetch";
import type { Middleware } from "openapi-fetch";

import { toApiRequestError } from "./errors";
import type { ApiPaths as paths } from "@parampara/contracts";

export type TokenSource = () => Promise<string | null>;

export function apiBase(): string {
  return process.env.NEXT_PUBLIC_API_BASE ?? "http://localhost:8000";
}

function authMiddleware(getToken: TokenSource): Middleware {
  return {
    async onRequest({ request }) {
      const token = await getToken();
      if (token) request.headers.set("Authorization", `Bearer ${token}`);
      return request;
    },
  };
}

/** One client per signed-in session; the token is read fresh on every request. */
export function createApiClient(getToken: TokenSource, baseUrl: string = apiBase()) {
  const client = createClient<paths>({ baseUrl });
  client.use(authMiddleware(getToken));
  return client;
}

export type ApiClient = ReturnType<typeof createApiClient>;

/** Unwraps an openapi-fetch result: returns data or throws an ApiRequestError. */
export function unwrap<T>(result: { data?: T; error?: unknown; response: Response }): T {
  if (result.error !== undefined || result.data === undefined) {
    throw toApiRequestError(result.response.status, result.error);
  }
  return result.data;
}
