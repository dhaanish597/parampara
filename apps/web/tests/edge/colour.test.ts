import { describe, expect, it } from "vitest";
import type { PartProfile } from "@parampara/contracts";
import {
  circlePixelFraction,
  hueDistanceDeg,
  matchesPartProfile,
  rectPixelFraction,
  rgbToHsv,
  type FrameBuffer,
} from "../../lib/edge/colour.js";

function makeSolidFrame(w: number, h: number, r: number, g: number, b: number): FrameBuffer {
  const data = new Uint8ClampedArray(w * h * 4);
  for (let i = 0; i < w * h; i++) {
    data[i * 4] = r;
    data[i * 4 + 1] = g;
    data[i * 4 + 2] = b;
    data[i * 4 + 3] = 255;
  }
  return { width: w, height: h, data };
}

const RED_PROFILE: PartProfile = {
  part_id: "wire_phase",
  h_deg: 2,
  s: 0.9,
  v: 0.85,
  tol_h_deg: 18,
  min_s: 0.5,
  min_v: 0.4,
  max_v: 1.0,
  dark: false,
};

const DARK_PROFILE: PartProfile = {
  part_id: "wire_neutral",
  h_deg: 0,
  s: 0.05,
  v: 0.12,
  tol_h_deg: 18,
  min_s: 0,
  min_v: 0,
  max_v: 0.24,
  dark: true,
};

describe("colour (BUILD_PLAN 17.2–17.3)", () => {
  it("converts primary RGB colours to HSV", () => {
    expect(rgbToHsv(255, 0, 0)).toEqual({ h: 0, s: 1, v: 1 });
    expect(rgbToHsv(0, 255, 0)).toEqual({ h: 120, s: 1, v: 1 });
    expect(rgbToHsv(0, 0, 255)).toEqual({ h: 240, s: 1, v: 1 });
    expect(rgbToHsv(0, 0, 0)).toEqual({ h: 0, s: 0, v: 0 });
  });

  it("handles red hue wrap-around across 0/360 degrees", () => {
    expect(hueDistanceDeg(355, 5)).toBe(10);
    expect(hueDistanceDeg(2, 350)).toBe(12);
    expect(matchesPartProfile(rgbToHsv(220, 10, 45), RED_PROFILE)).toBe(true);
    expect(matchesPartProfile(rgbToHsv(10, 200, 10), RED_PROFILE)).toBe(false);
  });

  it("matches dark parts by value and low saturation regardless of hue", () => {
    expect(matchesPartProfile({ h: 210, s: 0.15, v: 0.18 }, DARK_PROFILE)).toBe(true);
    expect(matchesPartProfile({ h: 0, s: 0.6, v: 0.15 }, DARK_PROFILE)).toBe(false);
    expect(matchesPartProfile({ h: 0, s: 0.05, v: 0.5 }, DARK_PROFILE)).toBe(false);
  });

  it("computes pixel fraction inside circles and rectangles", () => {
    const redFrame = makeSolidFrame(40, 40, 220, 20, 25);
    expect(circlePixelFraction(redFrame, 0.5, 0.5, 0.2, RED_PROFILE)).toBeGreaterThan(0.95);
    expect(rectPixelFraction(redFrame, 0.2, 0.2, 0.8, 0.8, RED_PROFILE)).toBeGreaterThan(0.95);
    expect(circlePixelFraction(redFrame, 0.5, 0.5, 0.2, DARK_PROFILE)).toBe(0);
  });
});
