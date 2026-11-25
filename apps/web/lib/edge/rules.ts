/**
 * Pure deterministic edge checks and hazard rules over a rolling window (BUILD_PLAN 17.4).
 */

import type {
  Calibration,
  EdgeCheck,
  EdgeEvent,
  Hazard,
  SkillGraph,
  Step,
  ZoneCalibration,
} from "@parampara/contracts";
import type { FrameFeatures } from "./features.js";

const DEFAULT_WINDOW_MS = 3000;
const EDGE_REARM_MS = 5000;
const PART_IN_ZONE_THRESHOLD = 0.15;
const RISK_COOLDOWN_MS = 3000;
const ORDER_COOLDOWN_MS = 5000;
const HAND_LOST_MS = 5000;
const MOTION_ACTIVE_MIN = 0.01;
const MOTION_SETTLED_MAX = 0.004;
const MOTION_ACTIVE_REQUIRED_MS = 2000;

export interface RuleEngine {
  step(
    feat: FrameFeatures,
    currentStepId: string,
    verifiedSteps: readonly string[],
  ): EdgeEvent[];
  rearmStep(stepId: string): void;
}

interface EngineState {
  buffer: FrameFeatures[];
  firedEdgeAt: Map<string, number>;
  lastRiskAt: Map<string, number>;
  lastOrderAt: Map<string, number>;
  lastHandSeenMs: number | null;
  handLostFired: boolean;
  motionActiveMs: number;
  lastStepId: string | null;
}

function sustainedSince(
  buffer: readonly FrameFeatures[],
  predicate: (f: FrameFeatures) => boolean,
): number {
  if (buffer.length === 0) return 0;
  const latest = buffer[buffer.length - 1]!;
  if (!predicate(latest)) return 0;
  let earliest = latest.t_ms;
  for (let i = buffer.length - 2; i >= 0; i--) {
    if (!predicate(buffer[i]!)) break;
    earliest = buffer[i]!.t_ms;
  }
  return latest.t_ms - earliest;
}

function computeBufferWindowMs(graph: SkillGraph): number {
  let maxNeeded = DEFAULT_WINDOW_MS;
  for (const s of graph.steps) {
    for (const c of s.edge_checks) {
      if (c.min_dwell_ms > maxNeeded) maxNeeded = c.min_dwell_ms;
    }
  }
  for (const h of graph.hazards) {
    const ms = h.rule.min_ms ?? 400;
    if (ms > maxNeeded) maxNeeded = ms;
  }
  return maxNeeded + 500;
}

function canFireEdgeKey(state: EngineState, key: string, nowMs: number): boolean {
  const prev = state.firedEdgeAt.get(key);
  return prev === undefined || nowMs - prev > EDGE_REARM_MS;
}

function checkPartInZone(
  buffer: readonly FrameFeatures[],
  stepId: string,
  check: EdgeCheck,
  state: EngineState,
): EdgeEvent | null {
  if (!check.part_id || !check.zone_id) return null;
  const now = buffer[buffer.length - 1]!.t_ms;
  const key = `${stepId}:${check.id}`;
  if (!canFireEdgeKey(state, key, now)) return null;
  const dur = sustainedSince(
    buffer,
    (f) =>
      (f.zone_part_fraction[check.zone_id!]?.[check.part_id!] ?? 0) >= PART_IN_ZONE_THRESHOLD &&
      !f.hand_in_zone[check.zone_id!],
  );
  if (dur < check.min_dwell_ms) return null;
  state.firedEdgeAt.set(key, now);
  return {
    kind: "edge_key",
    step_id: stepId,
    rule_or_check_id: check.id,
    part_id: check.part_id,
    zone_id: check.zone_id,
    t_ms: now,
  };
}

function checkHandsSettled(
  buffer: readonly FrameFeatures[],
  stepId: string,
  check: EdgeCheck,
  state: EngineState,
): EdgeEvent | null {
  const now = buffer[buffer.length - 1]!.t_ms;
  const key = `${stepId}:${check.id}`;
  if (!canFireEdgeKey(state, key, now) || state.motionActiveMs < MOTION_ACTIVE_REQUIRED_MS) {
    return null;
  }
  const dur = sustainedSince(
    buffer,
    (f) => f.hands.length > 0 && f.motion < MOTION_SETTLED_MAX,
  );
  if (dur < check.min_dwell_ms) return null;
  state.firedEdgeAt.set(key, now);
  return {
    kind: "edge_key",
    step_id: stepId,
    rule_or_check_id: check.id,
    t_ms: now,
    detail: { assurance: "single" },
  };
}

function checkHazardRule(
  buffer: readonly FrameFeatures[],
  hazard: Hazard,
  zones: Map<string, ZoneCalibration>,
  frameW: number,
  frameH: number,
  state: EngineState,
): EdgeEvent | null {
  const { rule } = hazard;
  if (rule.kind !== "wrong_part_near_zone" || !rule.part_id || !rule.forbidden_zone_id) return null;
  const zone = zones.get(rule.forbidden_zone_id);
  if (!zone) return null;
  const now = buffer[buffer.length - 1]!.t_ms;
  const prevFire = state.lastRiskAt.get(hazard.id);
  if (prevFire !== undefined && now - prevFire < RISK_COOLDOWN_MS) return null;
  const radius = rule.radius ?? 0.07;
  const minMs = rule.min_ms ?? 400;
  const minDim = Math.max(1, Math.min(frameW, frameH));
  const dur = sustainedSince(buffer, (f) =>
    f.hands.some(
      (h) =>
        h.held_part === rule.part_id &&
        Math.hypot((h.pinch_point.x - zone.x) * frameW, (h.pinch_point.y - zone.y) * frameH) /
          minDim <=
          radius,
    ),
  );
  if (dur < minMs) return null;
  state.lastRiskAt.set(hazard.id, now);
  return {
    kind: "risk",
    step_id: hazard.step_id,
    rule_or_check_id: hazard.id,
    part_id: rule.part_id,
    zone_id: rule.forbidden_zone_id,
    t_ms: now,
  };
}

function checkOutOfOrder(
  buffer: readonly FrameFeatures[],
  laterSteps: readonly Step[],
  currentStepId: string,
  state: EngineState,
): EdgeEvent[] {
  const out: EdgeEvent[] = [];
  const now = buffer[buffer.length - 1]!.t_ms;
  for (const step of laterSteps) {
    for (const check of step.edge_checks) {
      if (check.kind !== "part_in_zone" || !check.part_id || !check.zone_id) continue;
      const key = `${step.id}:${check.id}`;
      const prev = state.lastOrderAt.get(key);
      if (prev !== undefined && now - prev < ORDER_COOLDOWN_MS) continue;
      const dur = sustainedSince(
        buffer,
        (f) =>
          (f.zone_part_fraction[check.zone_id!]?.[check.part_id!] ?? 0) >= PART_IN_ZONE_THRESHOLD &&
          !f.hand_in_zone[check.zone_id!],
      );
      if (dur >= check.min_dwell_ms) {
        state.lastOrderAt.set(key, now);
        out.push({
          kind: "order_violation",
          step_id: currentStepId,
          rule_or_check_id: check.id,
          part_id: check.part_id,
          zone_id: check.zone_id,
          t_ms: now,
        });
      }
    }
  }
  return out;
}

function updateMotionAndHands(feat: FrameFeatures, state: EngineState): EdgeEvent | null {
  const prev = state.buffer[state.buffer.length - 1];
  const dt = prev ? Math.max(0, feat.t_ms - prev.t_ms) : 0;
  if (feat.motion > MOTION_ACTIVE_MIN) state.motionActiveMs += dt;
  if (feat.hands.length > 0) {
    state.lastHandSeenMs = feat.t_ms;
    state.handLostFired = false;
    return null;
  }
  if (
    state.lastHandSeenMs !== null &&
    !state.handLostFired &&
    feat.t_ms - state.lastHandSeenMs >= HAND_LOST_MS
  ) {
    state.handLostFired = true;
    return { kind: "hand_lost", step_id: null, rule_or_check_id: null, t_ms: feat.t_ms };
  }
  return null;
}

function runActiveStepChecks(
  buffer: readonly FrameFeatures[],
  activeStep: Step | undefined,
  currentStepId: string,
  verifiedSteps: readonly string[],
  state: EngineState,
): EdgeEvent[] {
  if (!activeStep || verifiedSteps.includes(currentStepId)) return [];
  const out: EdgeEvent[] = [];
  for (const check of activeStep.edge_checks) {
    const ev =
      check.kind === "part_in_zone"
        ? checkPartInZone(buffer, currentStepId, check, state)
        : checkHandsSettled(buffer, currentStepId, check, state);
    if (ev) out.push(ev);
  }
  return out;
}

function clearStepKeys(state: EngineState, stepId: string): void {
  const prefix = `${stepId}:`;
  for (const k of Array.from(state.firedEdgeAt.keys())) {
    if (k.startsWith(prefix)) state.firedEdgeAt.delete(k);
  }
}

function stepEngine(
  graph: SkillGraph, zones: Map<string, ZoneCalibration>, frameW: number, frameH: number,
  windowMs: number, state: EngineState, feat: FrameFeatures, currentStepId: string, verifiedSteps: readonly string[],
): EdgeEvent[] {
  if (state.lastStepId !== currentStepId) {
    state.motionActiveMs = 0;
    clearStepKeys(state, currentStepId);
    state.lastStepId = currentStepId;
  }
  const events: EdgeEvent[] = [];
  const handLost = updateMotionAndHands(feat, state);
  if (handLost) events.push(handLost);
  state.buffer.push(feat);
  const cutoff = feat.t_ms - windowMs;
  while (state.buffer.length > 0 && state.buffer[0]!.t_ms < cutoff) state.buffer.shift();
  const activeStep = graph.steps.find((s) => s.id === currentStepId);
  const verified = new Set(verifiedSteps);
  events.push(...runActiveStepChecks(state.buffer, activeStep, currentStepId, verifiedSteps, state));
  for (const hazard of graph.hazards) {
    const risk = checkHazardRule(state.buffer, hazard, zones, frameW, frameH, state);
    if (risk) events.push(risk);
  }
  if (!verified.has(currentStepId)) {
    const later = graph.steps.filter((s) => s.order > (activeStep?.order ?? 0) && !verified.has(s.id));
    events.push(...checkOutOfOrder(state.buffer, later, currentStepId, state));
  }
  return events;
}

export function createRuleEngine(graph: SkillGraph, calibration: Calibration): RuleEngine {
  const zones = new Map(calibration.zones.map((z) => [z.zone_id, z]));
  const windowMs = computeBufferWindowMs(graph);
  const frameW = calibration.frame_w || 320;
  const frameH = calibration.frame_h || 180;
  const state: EngineState = {
    buffer: [], firedEdgeAt: new Map(), lastRiskAt: new Map(), lastOrderAt: new Map(),
    lastHandSeenMs: null, handLostFired: false, motionActiveMs: 0, lastStepId: null,
  };
  return {
    rearmStep: (stepId) => clearStepKeys(state, stepId),
    step: (feat, currentStepId, verifiedSteps) =>
      stepEngine(graph, zones, frameW, frameH, windowMs, state, feat, currentStepId, verifiedSteps),
  };
}
