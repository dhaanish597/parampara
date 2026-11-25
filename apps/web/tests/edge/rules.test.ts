import { describe, expect, it } from "vitest";
import type { Calibration, SkillGraph } from "@parampara/contracts";
import { extractFrameFeatures, type FrameFeatures } from "../../lib/edge/features.js";
import { createRuleEngine } from "../../lib/edge/rules.js";
import { buildPartProfile } from "../../lib/edge/calibrate.js";
import type { FrameBuffer } from "../../lib/edge/colour.js";

const SKILL_GRAPH: SkillGraph = {
  schema_version: "1.0",
  title: { en: "3-way terminal block wiring", hi: "3-वे टर्मिनल ब्लॉक वायरिंग" },
  summary: { en: "Wire PE, N, L.", hi: "PE, N, L तार लगाएँ।" },
  domain: "electrical",
  parts: [
    { id: "wire_phase", name: { en: "Phase", hi: "फेज़" }, role: "phase", colour_hint: "red" },
    { id: "wire_neutral", name: { en: "Neutral", hi: "न्यूट्रल" }, role: "neutral", colour_hint: "black" },
    { id: "wire_earth", name: { en: "Earth", hi: "अर्थ" }, role: "earth", colour_hint: "green" },
  ],
  zones: [
    { id: "zone_PE", name: { en: "PE", hi: "PE" }, calibration_prompt: { en: "Tap PE", hi: "PE टैप करें" } },
    { id: "zone_N", name: { en: "N", hi: "N" }, calibration_prompt: { en: "Tap N", hi: "N टैप करें" } },
    { id: "zone_L", name: { en: "L", hi: "L" }, calibration_prompt: { en: "Tap L", hi: "L टैप करें" } },
  ],
  steps: [
    {
      id: "s1", order: 1, title: { en: "Check", hi: "जाँचें" }, instruction: { en: "Check ferrules", hi: "फेरूल जाँचें" },
      source_segment: { start_ms: 0, end_ms: 10000 },
      success_predicates: [{ id: "p1", kind: "object_state", description: "Ferrules visible" }],
      edge_checks: [{ id: "e1", kind: "hands_settled", min_dwell_ms: 800 }],
      common_errors: [], tips: [], expected_duration_s: 20, critical: false,
    },
    {
      id: "s2", order: 2, title: { en: "Earth", hi: "अर्थ" }, instruction: { en: "Green in PE", hi: "हरा PE में" },
      source_segment: { start_ms: 10000, end_ms: 20000 },
      success_predicates: [{ id: "p2", kind: "object_in_zone", description: "Green in PE", part_id: "wire_earth", zone_id: "zone_PE" }],
      edge_checks: [{ id: "e2", kind: "part_in_zone", min_dwell_ms: 1000, part_id: "wire_earth", zone_id: "zone_PE" }],
      common_errors: [], tips: [], expected_duration_s: 30, critical: true,
    },
    {
      id: "s3", order: 3, title: { en: "Neutral", hi: "न्यूट्रल" }, instruction: { en: "Black in N", hi: "काला N में" },
      source_segment: { start_ms: 20000, end_ms: 30000 },
      success_predicates: [{ id: "p3", kind: "object_in_zone", description: "Black in N", part_id: "wire_neutral", zone_id: "zone_N" }],
      edge_checks: [{ id: "e3", kind: "part_in_zone", min_dwell_ms: 1000, part_id: "wire_neutral", zone_id: "zone_N" }],
      common_errors: [], tips: [], expected_duration_s: 30, critical: true,
    },
    {
      id: "s4", order: 4, title: { en: "Phase", hi: "फेज़" }, instruction: { en: "Red in L", hi: "लाल L में" },
      source_segment: { start_ms: 30000, end_ms: 40000 },
      success_predicates: [{ id: "p4", kind: "object_in_zone", description: "Red in L", part_id: "wire_phase", zone_id: "zone_L" }],
      edge_checks: [{ id: "e4", kind: "part_in_zone", min_dwell_ms: 1000, part_id: "wire_phase", zone_id: "zone_L" }],
      common_errors: [], tips: [], expected_duration_s: 30, critical: true,
    },
  ],
  hazards: [
    {
      id: "h1", step_id: "s3", description: { en: "Phase near N", hi: "फेज़ N के पास" },
      severity: "critical",
      rule: { kind: "wrong_part_near_zone", part_id: "wire_phase", forbidden_zone_id: "zone_N", radius: 0.07, min_ms: 400 },
      interrupt_text: { en: "Stop!", hi: "रुको! लाल तार N में नहीं जाता।" },
    },
  ],
  credential_policy: {
    profile: "demo", min_consecutive_clean_runs: 1, mastery_threshold: 0.5,
    require_exam_mode: false, require_cosign: true,
  },
};

const CALIBRATION: Calibration = {
  zones: [
    { zone_id: "zone_PE", x: 0.2, y: 0.5, radius: 0.06 },
    { zone_id: "zone_N", x: 0.5, y: 0.5, radius: 0.06 },
    { zone_id: "zone_L", x: 0.8, y: 0.5, radius: 0.06 },
  ],
  parts: [], frame_w: 320, frame_h: 180, created_at: "2026-11-26T00:00:00Z",
};

function makeFeat(t_ms: number, overrides: Partial<FrameFeatures> = {}): FrameFeatures {
  return {
    t_ms, hands: [],
    zone_part_fraction: {
      zone_PE: { wire_earth: 0, wire_neutral: 0, wire_phase: 0 },
      zone_N: { wire_earth: 0, wire_neutral: 0, wire_phase: 0 },
      zone_L: { wire_earth: 0, wire_neutral: 0, wire_phase: 0 },
    },
    hand_in_zone: { zone_PE: false, zone_N: false, zone_L: false },
    motion: 0, ...overrides,
  };
}

describe("rules part_in_zone dwell (BUILD_PLAN 17.4)", () => {
  it("fires edge_key only after continuous dwell with hand out of zone", () => {
    const engine = createRuleEngine(SKILL_GRAPH, CALIBRATION);
    const peFull = { ...makeFeat(0).zone_part_fraction, zone_PE: { wire_earth: 0.3, wire_neutral: 0, wire_phase: 0 } };
    for (let t = 0; t <= 1200; t += 200) {
      const evs = engine.step(makeFeat(t, { zone_part_fraction: peFull, hand_in_zone: { zone_PE: true, zone_N: false, zone_L: false } }), "s2", ["s1"]);
      expect(evs.filter((e) => e.kind === "edge_key")).toHaveLength(0);
    }
    let fired = 0;
    for (let t = 1400; t <= 3000; t += 200) {
      const evs = engine.step(makeFeat(t, { zone_part_fraction: peFull }), "s2", ["s1"]);
      fired += evs.filter((e) => e.kind === "edge_key" && e.step_id === "s2").length;
    }
    expect(fired).toBe(1);
  });
});

describe("rules hazards and order (BUILD_PLAN 17.4)", () => {
  it("fires wrong_part_near_zone risk once after 400 ms and respects 3 s cooldown", () => {
    const engine = createRuleEngine(SKILL_GRAPH, CALIBRATION);
    const risks: number[] = [];
    for (let t = 0; t <= 4200; t += 100) {
      const evs = engine.step(makeFeat(t, {
        hands: [{
          handedness: "Right", pinch_point: { x: 0.51, y: 0.5 }, pinching: true,
          box: { minX: 0.45, minY: 0.45, maxX: 0.55, maxY: 0.55 },
          held_part: "wire_phase", landmarks: [],
        }],
      }), "s3", ["s1", "s2"]);
      for (const e of evs) if (e.kind === "risk") risks.push(e.t_ms);
    }
    expect(risks.length).toBe(2);
    expect(risks[0]).toBeGreaterThanOrEqual(400);
    expect(risks[1]! - risks[0]!).toBeGreaterThanOrEqual(3000);
  });

  it("detects out_of_order when a later step part settles early", () => {
    const engine = createRuleEngine(SKILL_GRAPH, CALIBRATION);
    const lFull = { ...makeFeat(0).zone_part_fraction, zone_L: { wire_earth: 0, wire_neutral: 0, wire_phase: 0.3 } };
    let orderViolations = 0;
    for (let t = 0; t <= 1600; t += 200) {
      orderViolations += engine.step(makeFeat(t, { zone_part_fraction: lFull }), "s2", ["s1"]).filter((e) => e.kind === "order_violation").length;
    }
    expect(orderViolations).toBe(1);
  });
});

describe("rules hands_settled and performance (BUILD_PLAN 17.4, T-013 AC3)", () => {
  it("fires hands_settled with single assurance only when a hand is in view", () => {
    const engine = createRuleEngine(SKILL_GRAPH, CALIBRATION);
    const hand = [{
      handedness: "Right" as const, pinch_point: { x: 0.2, y: 0.5 }, pinching: false,
      box: { minX: 0.15, minY: 0.45, maxX: 0.25, maxY: 0.55 },
      held_part: null, landmarks: [],
    }];
    const keys: Array<{ assurance: unknown }> = [];
    for (let t = 0; t <= 2200; t += 200) engine.step(makeFeat(t, { hands: hand, motion: 0.02 }), "s1", []);
    for (let t = 2400; t <= 3600; t += 200) {
      for (const e of engine.step(makeFeat(t, { hands: [], motion: 0.001 }), "s1", [])) {
        if (e.kind === "edge_key") keys.push({ assurance: e.detail?.assurance });
      }
    }
    expect(keys).toEqual([]);
    for (let t = 3800; t <= 5000; t += 200) {
      for (const e of engine.step(makeFeat(t, { hands: hand, motion: 0.001 }), "s1", [])) {
        if (e.kind === "edge_key") keys.push({ assurance: e.detail?.assurance });
      }
    }
    expect(keys).toEqual([{ assurance: "single" }]);
  });
});

describe("rules rearm, long dwell, and performance (T-013 AC3)", () => {
  it("re-arms edge_key via rearmStep, supports dwell > 3s, and skips out_of_order once verified", () => {
    const longGraph: SkillGraph = {
      ...SKILL_GRAPH,
      steps: [
        SKILL_GRAPH.steps[0]!,
        { ...SKILL_GRAPH.steps[1]!, edge_checks: [{ ...SKILL_GRAPH.steps[1]!.edge_checks[0]!, min_dwell_ms: 3600 }] },
        SKILL_GRAPH.steps[2]!,
        SKILL_GRAPH.steps[3]!,
      ],
    };
    const engine = createRuleEngine(longGraph, CALIBRATION);
    const peFull = { ...makeFeat(0).zone_part_fraction, zone_PE: { wire_earth: 0.3, wire_neutral: 0, wire_phase: 0 } };
    let fired = 0;
    for (let t = 0; t <= 3800; t += 200) {
      fired += engine.step(makeFeat(t, { zone_part_fraction: peFull }), "s2", ["s1"]).filter((e) => e.kind === "edge_key").length;
    }
    expect(fired).toBe(1);
    engine.rearmStep("s2");
    fired += engine.step(makeFeat(4000, { zone_part_fraction: peFull }), "s2", ["s1"]).filter((e) => e.kind === "edge_key").length;
    expect(fired).toBe(2);
    const lFull = { ...makeFeat(0).zone_part_fraction, zone_L: { wire_earth: 0, wire_neutral: 0, wire_phase: 0.3 } };
    let orderEvents = 0;
    for (let t = 4200; t <= 5800; t += 200) {
      orderEvents += engine.step(makeFeat(t, { zone_part_fraction: lFull }), "s2", ["s1", "s2"]).filter((e) => e.kind === "order_violation").length;
    }
    expect(orderEvents).toBe(0);
  });
});

describe("rules performance (T-013 AC3)", () => {
  it("runs features + rules with hands under 12 ms per 320x180 frame", () => {
    const buf: FrameBuffer = { width: 320, height: 180, data: new Uint8ClampedArray(320 * 180 * 4).fill(180) };
    const cal: Calibration = {
      ...CALIBRATION,
      parts: [buildPartProfile("wire_phase", [{ width: 10, height: 10, data: new Uint8ClampedArray(400).fill(200) }])],
    };
    const lm = Array.from({ length: 21 }, (_, idx) => ({ x: 0.5 + (idx % 3) * 0.01, y: 0.5, z: 0 }));
    const engine = createRuleEngine(SKILL_GRAPH, cal);
    const t0 = performance.now();
    for (let i = 0; i < 20; i++) {
      engine.step(extractFrameFeatures({ t_ms: i * 66, frame: buf, hands: [{ landmarks: lm, handedness: "Right" }], calibration: cal }), "s2", ["s1"]);
    }
    expect((performance.now() - t0) / 20).toBeLessThan(12);
  });
});
