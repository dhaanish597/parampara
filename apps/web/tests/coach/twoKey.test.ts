import { describe, expect, it } from "vitest";
import type { EdgeEvent, VerifierVerdict } from "@parampara/contracts";
import { createTwoKeyTracker } from "../../lib/coach/twoKey.js";

function edge(stepId: string, tMs: number, single = false): EdgeEvent {
  return {
    kind: "edge_key",
    step_id: stepId,
    rule_or_check_id: "e2",
    t_ms: tMs,
    detail: single ? { assurance: "single" } : undefined,
  };
}

function verdict(status: VerifierVerdict["status"], confidence = 0.9): VerifierVerdict {
  return {
    status,
    confidence,
    predicate_results: [],
    visible_issues: [],
    coach_hint_hi: "ठीक है",
    frame_sha256: "a".repeat(64),
    model: "gemini-3.5-flash",
    latency_ms: 1200,
  };
}

describe("twoKey ordering and window (BUILD_PLAN 18.1-18.2)", () => {
  it("completes when edge arrives first then passing VLM within 5 s", () => {
    const t = createTwoKeyTracker();
    expect(t.recordEdgeKey(edge("s2", 1000)).completed).toBe(false);
    const res = t.recordVerdict("s2", 4500, verdict("pass", 0.85));
    expect(res.completed).toBe(true);
    expect(res.assurance).toBe("two_key");
  });

  it("completes when VLM arrives first then edge within 5 s", () => {
    const t = createTwoKeyTracker();
    expect(t.recordVerdict("s3", 2000, verdict("pass", 0.7)).completed).toBe(false);
    const res = t.recordEdgeKey(edge("s3", 6900));
    expect(res.completed).toBe(true);
    expect(res.assurance).toBe("two_key");
  });

  it("rejects completion outside 5 s window or below 0.7 confidence", () => {
    const t = createTwoKeyTracker();
    t.recordEdgeKey(edge("s2", 1000));
    const late = t.recordVerdict("s2", 7000, verdict("pass", 0.95));
    expect(late.completed).toBe(false);
    expect(late.expiredKey).toBe(true);

    t.recordEdgeKey(edge("s4", 1000));
    const lowConf = t.recordVerdict("s4", 1200, verdict("pass", 0.65));
    expect(lowConf.completed).toBe(false);
  });
});

describe("twoKey single and manual assurance (BUILD_PLAN 18.1 & 18.3)", () => {
  it("records single assurance for hands_settled edge checks", () => {
    const t = createTwoKeyTracker();
    t.recordEdgeKey(edge("s1", 1000, true));
    const res = t.recordVerdict("s1", 1500, verdict("pass", 0.9));
    expect(res.completed).toBe(true);
    expect(res.assurance).toBe("single");
  });

  it("allows manual confirm only after two consecutive unavailable verdicts and locks assurance", () => {
    const t = createTwoKeyTracker();
    expect(t.confirmManually("s3").completed).toBe(false);
    t.recordVerdict("s3", 1000, verdict("unavailable", 0));
    t.recordVerdict("s3", 1500, verdict("fail", 0.9));
    t.recordVerdict("s3", 2000, verdict("unavailable", 0));
    expect(t.isManualConfirmAllowed("s3")).toBe(false);
    t.recordVerdict("s3", 3000, verdict("unavailable", 0));
    expect(t.isManualConfirmAllowed("s3")).toBe(true);
    const manual = t.confirmManually("s3");
    expect(manual.completed).toBe(true);
    expect(manual.assurance).toBe("manual");
    const afterEdge = t.recordEdgeKey(edge("s3", 3500));
    expect(afterEdge.assurance).toBe("manual");
  });

  it("gates by active step and tracks in-flight verify with 8 s timeout", () => {
    const t = createTwoKeyTracker();
    t.setCurrentStep("s2");
    expect(t.recordEdgeKey(edge("s3", 1000)).completed).toBe(false);
    expect(t.recordVerdict("s3", 1200, verdict("pass", 0.95)).completed).toBe(false);
    t.markVerifyInFlight("s2", 1000);
    expect(t.isVerifyInFlight("s2", 5000)).toBe(true);
    expect(t.isVerifyInFlight("s2", 9500)).toBe(false);
    t.markVerifyInFlight("s2", 10000);
    t.recordVerdict("s2", 10500, verdict("fail", 0.9));
    expect(t.isVerifyInFlight("s2", 10600)).toBe(false);
  });
});
