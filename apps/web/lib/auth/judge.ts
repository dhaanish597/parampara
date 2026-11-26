/** "Try as judge": anonymous Supabase sign-in, then demo join (BUILD_PLAN 4.2, 12.2, 25.2). */
import type { SupabaseClient } from "@supabase/supabase-js";

import { unwrap } from "../api/client";
import type { ApiClient } from "../api/client";
import type { Me } from "../api/types";

export async function loadMe(api: ApiClient): Promise<Me> {
  // The route returns an untyped dict until it declares a response model (types.ts).
  return unwrap(await api.GET("/v1/me")) as unknown as Me;
}

export async function signInAsJudge(supabase: SupabaseClient, api: ApiClient): Promise<Me> {
  const { error } = await supabase.auth.signInAnonymously();
  if (error) throw error;
  unwrap(await api.POST("/v1/demo/join"));
  return loadMe(api);
}
