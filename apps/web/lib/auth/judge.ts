/** "Try as judge": anonymous Supabase sign-in, then demo join (BUILD_PLAN 4.2, 12.2, 25.2). */
import type { SupabaseClient } from "@supabase/supabase-js";

import type { ApiClient } from "../api/client";
import { getMe, joinDemo } from "../api/endpoints";
import type { Me } from "../api/types";

export const loadMe = getMe;

export async function signInAsJudge(supabase: SupabaseClient, api: ApiClient): Promise<Me> {
  const { error } = await supabase.auth.signInAnonymously();
  if (error) throw error;
  try {
    await joinDemo(api);
    return await loadMe(api);
  } catch (err) {
    // Do not leave a half-joined anonymous session behind; the next try starts clean.
    await supabase.auth.signOut().catch(() => undefined);
    throw err;
  }
}

/** A judge whose demo membership is gone (for example after a database reset) rejoins once. */
export async function loadOrRejoin(api: ApiClient, isAnonymous: boolean): Promise<Me> {
  const me = await getMe(api);
  if (me.memberships.length > 0 || !isAnonymous) return me;
  await joinDemo(api);
  return getMe(api);
}
