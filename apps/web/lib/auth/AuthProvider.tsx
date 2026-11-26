"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { createApiClient } from "../api/client";
import type { ApiClient, TokenSource } from "../api/client";
import type { Me, MemberRole } from "../api/types";
import { readStored, writeStored } from "../storage";
import { getSupabase } from "../supabase/client";
import { loadOrRejoin, signInAsJudge } from "./judge";
import { pickActiveRole, restoreOutcome, rolesOf } from "./roles";

const ROLE_KEY = "parampara.activeRole";

/** "error": a Supabase session exists but the API could not load the profile (retryable). */
export type AuthStatus =
  | "loading"
  | "unavailable"
  | "signedOut"
  | "signingIn"
  | "signedIn"
  | "error";

interface AuthValue {
  status: AuthStatus;
  me: Me | null;
  roles: MemberRole[];
  activeRole: MemberRole | null;
  error: unknown;
  api: ApiClient;
  getToken: TokenSource;
  tryAsJudge: () => Promise<void>;
  signOut: () => Promise<void>;
  setActiveRole: (role: MemberRole) => void;
  retry: () => void;
}

const AuthContext = createContext<AuthValue | null>(null);

async function currentToken(): Promise<string | null> {
  const result = await getSupabase()?.auth.getSession();
  return result?.data.session?.access_token ?? null;
}

interface Setters {
  setStatus: (status: AuthStatus) => void;
  setMe: (me: Me | null) => void;
  setError: (error: unknown) => void;
}

/** Loads /v1/me for an existing session. A 401 means the session is stale: sign it out. */
async function loadSignedIn(
  api: ApiClient,
  isAnonymous: boolean,
  isCancelled: () => boolean,
  s: Setters,
) {
  try {
    const me = await loadOrRejoin(api, isAnonymous);
    if (isCancelled()) return;
    s.setMe(me);
    s.setError(null);
    s.setStatus("signedIn");
  } catch (err) {
    if (isCancelled()) return;
    if (restoreOutcome(err) === "signOut") {
      await getSupabase()?.auth.signOut().catch(() => undefined);
      s.setMe(null);
      return s.setStatus("signedOut");
    }
    s.setError(err);
    s.setStatus("error");
  }
}

/** Restores the session on load and follows sign-outs from other tabs or failed refreshes. */
function useRestoreSession(api: ApiClient, attempt: number, s: Setters) {
  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return s.setStatus("unavailable");
    let cancelled = false;
    s.setStatus("loading");
    void supabase.auth.getSession().then(({ data }) => {
      if (cancelled) return;
      if (!data.session) return s.setStatus("signedOut");
      void loadSignedIn(api, data.session.user.is_anonymous ?? false, () => cancelled, s);
    });
    const { data } = supabase.auth.onAuthStateChange((event) => {
      if (event !== "SIGNED_OUT" || cancelled) return;
      s.setMe(null);
      s.setStatus("signedOut");
    });
    return () => {
      cancelled = true;
      data.subscription.unsubscribe();
    };
  }, [api, attempt, s]);
}

function useJudgeActions(api: ApiClient, s: Setters) {
  const tryAsJudge = useCallback(async () => {
    const supabase = getSupabase();
    if (!supabase) return s.setStatus("unavailable");
    s.setStatus("signingIn");
    s.setError(null);
    try {
      s.setMe(await signInAsJudge(supabase, api));
      s.setStatus("signedIn");
    } catch (err) {
      s.setError(err);
      s.setStatus("signedOut");
    }
  }, [api, s]);

  const signOut = useCallback(async () => {
    await getSupabase()?.auth.signOut().catch(() => undefined);
    s.setMe(null);
    s.setStatus("signedOut");
  }, [s]);
  return { tryAsJudge, signOut };
}

function useSavedRole() {
  const [savedRole, setSavedRole] = useState<string | null>(null);
  useEffect(() => setSavedRole(readStored(ROLE_KEY)), []);
  const setActiveRole = useCallback((role: MemberRole) => {
    writeStored(ROLE_KEY, role);
    setSavedRole(role);
  }, []);
  return { savedRole, setActiveRole };
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const api = useMemo(() => createApiClient(currentToken), []);
  const [status, setStatus] = useState<AuthStatus>("loading");
  const [me, setMe] = useState<Me | null>(null);
  const [error, setError] = useState<unknown>(null);
  const setters = useMemo(() => ({ setStatus, setMe, setError }), []);
  const [attempt, setAttempt] = useState(0);
  const retry = useCallback(() => setAttempt((n) => n + 1), []);
  useRestoreSession(api, attempt, setters);
  const { tryAsJudge, signOut } = useJudgeActions(api, setters);
  const { savedRole, setActiveRole } = useSavedRole();

  const value = useMemo<AuthValue>(() => {
    const roles = rolesOf(me);
    return {
      status, me, roles, activeRole: pickActiveRole(roles, savedRole), error, api,
      getToken: currentToken, tryAsJudge, signOut, setActiveRole, retry,
    };
  }, [status, me, savedRole, error, api, tryAsJudge, signOut, setActiveRole, retry]);
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
