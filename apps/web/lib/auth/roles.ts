/** Role helpers for the role switcher (BUILD_PLAN 4.1). Pure. */
import { ApiRequestError } from "../api/errors";
import type { Me, MemberRole } from "../api/types";

/** Order the switcher shows roles in: the five journeys' order (4.2). */
export const ROLE_ORDER: readonly MemberRole[] = [
  "master",
  "supervisor",
  "trainee",
  "lab_buyer",
  "owner",
];

export function rolesOf(me: Me | null, orgId?: string): MemberRole[] {
  if (!me) return [];
  const membership = orgId ? me.memberships.find((m) => m.org_id === orgId) : me.memberships[0];
  const held = new Set(membership?.roles ?? []);
  return ROLE_ORDER.filter((role) => held.has(role));
}

/** Keep the saved role if the user still holds it, otherwise the first held role. */
export function pickActiveRole(held: MemberRole[], saved: string | null): MemberRole | null {
  const match = held.find((role) => role === saved);
  return match ?? held[0] ?? null;
}

export function primaryOrgId(me: Me | null): string | null {
  return me?.memberships[0]?.org_id ?? null;
}

/** What to do when a stored session cannot load /v1/me: a 401 means the session is stale. */
export function restoreOutcome(error: unknown): "signOut" | "retry" {
  return error instanceof ApiRequestError && error.status === 401 ? "signOut" : "retry";
}
