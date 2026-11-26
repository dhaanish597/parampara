/** Browser Supabase client (BUILD_PLAN 9.3, 27). Only the anon key is ever in the browser. */
import { createClient } from "@supabase/supabase-js";
import type { SupabaseClient } from "@supabase/supabase-js";

let client: SupabaseClient | null = null;

/** Returns the shared client, or null when the public Supabase env is not configured. */
export function getSupabase(): SupabaseClient | null {
  if (client) return client;
  const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
  const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
  if (!url || !anonKey) return null;
  client = createClient(url, anonKey, { auth: { persistSession: true, autoRefreshToken: true } });
  return client;
}
