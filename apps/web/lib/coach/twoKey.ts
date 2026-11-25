/**
 * Pure two-key step verification coordinator (BUILD_PLAN 18.1-18.3).
 * Completes a step only when edge_key and passing VLM verdict (confidence >= 0.7)
 * agree within 5,000 ms, or after explicit manual confirm following 2 consecutive
 * unavailable verdicts.
 */

import type { EdgeEvent, VerifierVerdict } from "@parampara/contracts";

export const TWO_KEY_WINDOW_MS = 5000;
export const VLM_CONFIDENCE_THRESHOLD = 0.7;
export const VERIFY_TIMEOUT_MS = 8000;

export type StepAssurance = "two_key" | "single" | "manual";

export interface TwoKeyResult {
  readonly completed: boolean;
  readonly assurance?: StepAssurance;
  readonly manualConfirmAllowed: boolean;
  readonly expiredKey: boolean;
  readonly inFlight: boolean;
}

interface StepKeyState {
  edgeAtMs: number | null;
  edgeSingle: boolean;
  vlmAtMs: number | null;
  vlmPass: boolean;
  consecutiveUnavailable: number;
  completed: boolean;
  completedAssurance?: StepAssurance;
  inFlightSinceMs: number | null;
}

export interface TwoKeyTracker {
  setCurrentStep(stepId: string | null): void;
  markVerifyInFlight(stepId: string, startedAtMs: number): void;
  isVerifyInFlight(stepId: string, nowMs?: number): boolean;
  recordEdgeKey(event: EdgeEvent): TwoKeyResult;
  recordVerdict(stepId: string, frameTMs: number, verdict: VerifierVerdict): TwoKeyResult;
  confirmManually(stepId: string): TwoKeyResult;
  isManualConfirmAllowed(stepId: string): boolean;
}

function getOrInit(map: Map<string, StepKeyState>, stepId: string): StepKeyState {
  let st = map.get(stepId);
  if (!st) {
    st = {
      edgeAtMs: null,
      edgeSingle: false,
      vlmAtMs: null,
      vlmPass: false,
      consecutiveUnavailable: 0,
      completed: false,
      inFlightSinceMs: null,
    };
    map.set(stepId, st);
  }
  return st;
}

function evaluate(st: StepKeyState): TwoKeyResult {
  const manualAllowed = !st.completed && st.consecutiveUnavailable >= 2;
  const inFlight = st.inFlightSinceMs !== null;
  if (st.completed) {
    return {
      completed: true,
      assurance: st.completedAssurance ?? "two_key",
      manualConfirmAllowed: false,
      expiredKey: false,
      inFlight: false,
    };
  }
  if (st.edgeAtMs === null || st.vlmAtMs === null || !st.vlmPass) {
    return { completed: false, manualConfirmAllowed: manualAllowed, expiredKey: false, inFlight };
  }
  if (Math.abs(st.edgeAtMs - st.vlmAtMs) <= TWO_KEY_WINDOW_MS) {
    st.completed = true;
    st.completedAssurance = st.edgeSingle ? "single" : "two_key";
    return {
      completed: true,
      assurance: st.completedAssurance,
      manualConfirmAllowed: false,
      expiredKey: false,
      inFlight: false,
    };
  }
  return { completed: false, manualConfirmAllowed: manualAllowed, expiredKey: true, inFlight };
}

function applyVerdict(
  st: StepKeyState,
  frameTMs: number,
  verdict: VerifierVerdict,
): TwoKeyResult {
  if (verdict.status === "unavailable") {
    st.consecutiveUnavailable += 1;
    return evaluate(st);
  }
  st.consecutiveUnavailable = 0;
  if (verdict.status === "pass" && verdict.confidence >= VLM_CONFIDENCE_THRESHOLD) {
    st.vlmAtMs = frameTMs;
    st.vlmPass = true;
  } else {
    st.vlmPass = false;
  }
  return evaluate(st);
}

function checkInFlight(st: StepKeyState, nowMs?: number): boolean {
  if (st.inFlightSinceMs === null) return false;
  if (nowMs !== undefined && nowMs - st.inFlightSinceMs > VERIFY_TIMEOUT_MS) {
    st.inFlightSinceMs = null;
    return false;
  }
  return true;
}

function applyEdgeKey(
  states: Map<string, StepKeyState>,
  activeStepId: string | null,
  event: EdgeEvent,
): TwoKeyResult {
  if (event.kind !== "edge_key" || !event.step_id) {
    return { completed: false, manualConfirmAllowed: false, expiredKey: false, inFlight: false };
  }
  const st = getOrInit(states, event.step_id);
  if (st.completed || (activeStepId !== null && event.step_id !== activeStepId)) return evaluate(st);
  st.edgeAtMs = event.t_ms;
  st.edgeSingle = event.detail?.assurance === "single";
  return evaluate(st);
}

function applyManual(st: StepKeyState): TwoKeyResult {
  if (st.completed) return evaluate(st);
  if (st.consecutiveUnavailable < 2) {
    return { completed: false, manualConfirmAllowed: false, expiredKey: false, inFlight: st.inFlightSinceMs !== null };
  }
  st.completed = true;
  st.completedAssurance = "manual";
  return evaluate(st);
}

export function createTwoKeyTracker(): TwoKeyTracker {
  const states = new Map<string, StepKeyState>();
  let activeStepId: string | null = null;
  return {
    setCurrentStep: (stepId) => { activeStepId = stepId; },
    markVerifyInFlight: (stepId, startedAtMs) => { getOrInit(states, stepId).inFlightSinceMs = startedAtMs; },
    isVerifyInFlight: (stepId, nowMs) => checkInFlight(getOrInit(states, stepId), nowMs),
    recordEdgeKey: (event) => applyEdgeKey(states, activeStepId, event),
    recordVerdict(stepId, frameTMs, verdict) {
      const st = getOrInit(states, stepId);
      st.inFlightSinceMs = null;
      if (st.completed || (activeStepId !== null && stepId !== activeStepId)) return evaluate(st);
      return applyVerdict(st, frameTMs, verdict);
    },
    confirmManually: (stepId) => applyManual(getOrInit(states, stepId)),
    isManualConfirmAllowed: (stepId) => {
      const st = getOrInit(states, stepId);
      return !st.completed && st.consecutiveUnavailable >= 2;
    },
  };
}
