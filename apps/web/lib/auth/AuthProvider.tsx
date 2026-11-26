"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import type { ReactNode } from "react";

import { createApiClient } from "../api/client";
import type { ApiClient, TokenSource } from "../api/client";
import type { Me, MemberRole } from "../api/types";
import { readStored, writeStored } from "../storage";
import { getSupabase } from "../supabase/client";
import { loadMe, signInAsJudge } from "./judge";
import { pickActiveRole, rolesOf } from "./roles";

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

/** Restores an existing Supabase session on load and fetches /v1/me. */
function useRestoreSession(
  api: ApiClient,
  attempt: number,
  { setStatus, setMe, setError }: Setters,
) {
  useEffect(() => {
    const supabase = getSupabase();
    if (!supabase) return setStatus("unavailable");
    setStatus("loading");
    void supabase.auth.getSession().then(async ({ data }) => {
      if (!data.session) return setStatus("signedOut");
      try {
        setMe(await loadMe(api));
        setError(null);
        setStatus("signedIn");
      } catch (err) {
        setError(err);
        setStatus("error");
      }
    });
  }, [api, attempt, setStatus, setMe, setError]);
}

function useJudgeActions(api: ApiClient, { setStatus, setMe, setError }: Setters) {
  const tryAsJudge = useCallback(async () => {
    const supabase = getSupabase();
    if (!supabase) return setStatus("unavailable");
    setStatus("signingIn");
    setError(null);
    try {
      setMe(await signInAsJudge(supabase, api));
      setStatus("signedIn");
    } catch (err) {
      setError(err);
      setStatus("signedOut");
    }
  }, [api, setStatus, setMe, setError]);

  const signOut = useCallback(async () => {
    await getSupabase()?.auth.signOut();
    setMe(null);
    setStatus("signedOut");
  }, [setMe, setStatus]);
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

  const roles = rolesOf(me);
  const activeRole = pickActiveRole(roles, savedRole);
  const value: AuthValue = {
    status, me, roles, activeRole, error, api, getToken: currentToken, tryAsJudge, signOut,
    setActiveRole, retry,
  };
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthValue {
  const value = useContext(AuthContext);
  if (!value) throw new Error("useAuth() must be used inside <AuthProvider>");
  return value;
}
