import { describe, expect, it } from "vitest";
import type { Calibration } from "@parampara/contracts";
import type { FrameBuffer } from "../../lib/edge/colour.js";
import { buildPartProfile } from "../../lib/edge/calibrate.js";
import { extractFrameFeatures, type HandLandmark } from "../../lib/edge/features.js";

function makeCanvas(w: number, h: number): FrameBuffer {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < w * h; i++) {
    data[i * 4] = 235;
    data[i * 4 + 1] = 235;
    data[i * 4 + 2] = 235;
    data[i * 4 + 3] = 255;
  }
  return { width: w, height: h, data };
}

function paintCircle(
  buf: FrameBuffer, cx: number, cy: number, rNorm: number, rgb: [number, number, number],
): void {
  const px = cx * buf.width;
  const py = cy * buf.height;
  const pr = rNorm * Math.min(buf.width, buf.height);
  for (let y = 0; y < buf.height; y++) {
    for (let x = 0; x < buf.width; x++) {
      if ((x - px) ** 2 + (y - py) ** 2 <= pr * pr) {
        const idx = (y * buf.width + x) * 4;
        buf.data[idx] = rgb[0];
        buf.data[idx + 1] = rgb[1];
        buf.data[idx + 2] = rgb[2];
      }
    }
  }
}

function makeHand(cx: number, cy: number, spread = 0.04): HandLandmark[] {
  return Array.from({ length: 21 }, (_, idx) => {
    const angle = (idx / 21) * Math.PI * 2;
    const r = idx === 4 || idx === 8 ? 0.01 : spread;
    return { x: cx + Math.cos(angle) * r, y: cy + Math.sin(angle) * r, z: 0 };
  });
}

function makeCalibration(): Calibration {
  const mk = (r: number, g: number, b: number): FrameBuffer => {
    const f = makeCanvas(30, 30);
    paintCircle(f, 0.5, 0.5, 0.5, [r, g, b]);
    return f;
  };
  return {
    zones: [
      { zone_id: "zone_PE", x: 0.2, y: 0.5, radius: 0.07 },
      { zone_id: "zone_N", x: 0.5, y: 0.5, radius: 0.07 },
      { zone_id: "zone_L", x: 0.8, y: 0.5, radius: 0.07 },
    ],
    parts: [
      buildPartProfile("wire_phase", [mk(220, 20, 25)]),
      buildPartProfile("wire_neutral", [mk(20, 20, 22)]),
      buildPartProfile("wire_earth", [mk(25, 185, 45)]),
    ],
    frame_w: 320, frame_h: 180, created_at: "2026-11-26T00:00:00Z",
  };
}

describe("features held part and zones (BUILD_PLAN 17.2)", () => {
  it("detects held red, black (dark), and green parts plus zone fractions", () => {
    const cal = makeCalibration();
    const cases: Array<["wire_phase" | "wire_neutral" | "wire_earth", [number, number, number]]> = [
      ["wire_phase", [220, 20, 25]],
      ["wire_neutral", [20, 20, 22]],
      ["wire_earth", [25, 185, 45]],
    ];
    for (const [partId, rgb] of cases) {
      const frame = makeCanvas(160, 120);
      paintCircle(frame, 0.5, 0.5, 0.06, rgb);
      const feat = extractFrameFeatures({
        t_ms: 100, frame, hands: [{ landmarks: makeHand(0.5, 0.5), handedness: "Right" }], calibration: cal,
      });
      expect(feat.hands[0]?.held_part).toBe(partId);
      expect(feat.hands[0]?.pinching).toBe(true);
      expect(feat.hand_in_zone["zone_N"]).toBe(true);
      expect(feat.zone_part_fraction["zone_N"]?.[partId]).toBeGreaterThan(0.2);
    }
  });
});

describe("features motion (BUILD_PLAN 17.2)", () => {
  it("computes hand motion by handedness so swapped array order yields zero motion", () => {
    const cal = makeCalibration();
    const frame = makeCanvas(160, 120);
    const left = { landmarks: makeHand(0.2, 0.2), handedness: "Left" as const };
    const right = { landmarks: makeHand(0.8, 0.2), handedness: "Right" as const };
    const prev = extractFrameFeatures({ t_ms: 0, frame, hands: [left, right], calibration: cal });
    const swapped = extractFrameFeatures({ t_ms: 100, frame, hands: [right, left], calibration: cal, prev });
    expect(swapped.motion).toBeCloseTo(0, 6);

    const moved = extractFrameFeatures({
      t_ms: 200, frame,
      hands: [{ landmarks: makeHand(0.25, 0.2), handedness: "Left" }, right],
      calibration: cal, prev: swapped,
    });
    expect(moved.motion).toBeGreaterThan(0.02);
  });
});
