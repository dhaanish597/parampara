import { describe, expect, it } from "vitest";
import type { FrameBuffer } from "../../lib/edge/colour.js";
import {
  buildPartProfile,
  buildZoneCalibration,
  checkProfileOverlap,
} from "../../lib/edge/calibrate.js";

function makeSolid(w: number, h: number, r: number, g: number, b: number): FrameBuffer {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < w * h; i++) {
    data[i * 4] = r;
    data[i * 4 + 1] = g;
    data[i * 4 + 2] = b;
    data[i * 4 + 3] = 255;
  }
  return { width: w, height: h, data };
}

describe("calibrate zones and parts (BUILD_PLAN 17.3)", () => {
  it("clamps zone radius to [0.03, 0.12] with default 0.06", () => {
    expect(buildZoneCalibration("zone_L", 0.25, 0.5).radius).toBe(0.06);
    expect(buildZoneCalibration("zone_N", 0.5, 0.5, 0.01).radius).toBe(0.03);
    expect(buildZoneCalibration("zone_PE", 0.75, 0.5, 0.5).radius).toBe(0.12);
  });

  it("builds coloured and dark part profiles from centre box samples", () => {
    const red = buildPartProfile("wire_phase", [makeSolid(50, 50, 220, 20, 20)]);
    expect(red.dark).toBe(false);
    expect(red.tol_h_deg).toBe(18);
    expect(red.h_deg).toBeLessThan(15);

    const black = buildPartProfile("wire_neutral", [makeSolid(50, 50, 22, 22, 24)]);
    expect(black.dark).toBe(true);
    expect(black.max_v).toBeLessThanOrEqual(0.25);
  });
});

describe("calibrate overlap quality gate (BUILD_PLAN 17.3)", () => {
  it("detects overlapping part profiles (>20% cross-match) and passes distinct ones", () => {
    const redFrame = makeSolid(40, 40, 220, 20, 20);
    const greenFrame = makeSolid(40, 40, 20, 190, 40);
    const nearRedFrame = makeSolid(40, 40, 230, 35, 20);
    const red = buildPartProfile("wire_phase", [redFrame]);
    const green = buildPartProfile("wire_earth", [greenFrame]);
    const nearRed = buildPartProfile("wire_dup", [nearRedFrame]);

    const ok = checkProfileOverlap([
      { profile: red, samples: [redFrame] },
      { profile: green, samples: [greenFrame] },
    ]);
    expect(ok.ok).toBe(true);
    expect(ok.overlaps).toHaveLength(0);

    const bad = checkProfileOverlap([
      { profile: red, samples: [redFrame] },
      { profile: nearRed, samples: [nearRedFrame] },
    ]);
    expect(bad.ok).toBe(false);
    expect(bad.overlaps.length).toBeGreaterThan(0);
  });
});
