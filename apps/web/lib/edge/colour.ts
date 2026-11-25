/**
 * Pure HSV colour matching and region pixel-fraction helpers (BUILD_PLAN 17.2–17.3).
 * Exemplar pure TypeScript module: zero browser API imports, generated contract types only.
 */

import type { PartProfile } from "@parampara/contracts";

export interface FrameBuffer {
  readonly width: number;
  readonly height: number;
  readonly data: Uint8ClampedArray;
}

export interface HsvColor {
  readonly h: number; // 0..360
  readonly s: number; // 0..1
  readonly v: number; // 0..1
}

export function rgbToHsv(r: number, g: number, b: number): HsvColor {
  const rn = r / 255;
  const gn = g / 255;
  const bn = b / 255;
  const max = Math.max(rn, gn, bn);
  const min = Math.min(rn, gn, bn);
  const d = max - min;
  let h = 0;
  if (d > 0) {
    if (max === rn) h = 60 * (((gn - bn) / d) % 6);
    else if (max === gn) h = 60 * ((bn - rn) / d + 2);
    else h = 60 * ((rn - gn) / d + 4);
  }
  if (h < 0) h += 360;
  return { h, s: max === 0 ? 0 : d / max, v: max };
}

export function hueDistanceDeg(a: number, b: number): number {
  const diff = Math.abs(a - b) % 360;
  return diff > 180 ? 360 - diff : diff;
}

export function matchesPartProfile(hsv: HsvColor, profile: PartProfile): boolean {
  if (profile.dark) {
    return hsv.v <= profile.max_v && hsv.s <= 0.35;
  }
  return (
    hueDistanceDeg(hsv.h, profile.h_deg) <= profile.tol_h_deg &&
    hsv.s >= profile.min_s &&
    hsv.v >= profile.min_v &&
    hsv.v <= profile.max_v
  );
}

export function rectPixelFraction(
  frame: FrameBuffer,
  minX: number,
  minY: number,
  maxX: number,
  maxY: number,
  profile: PartProfile,
): number {
  const x0 = Math.max(0, Math.floor(minX * frame.width));
  const y0 = Math.max(0, Math.floor(minY * frame.height));
  const x1 = Math.min(frame.width - 1, Math.ceil(maxX * frame.width));
  const y1 = Math.min(frame.height - 1, Math.ceil(maxY * frame.height));
  let total = 0;
  let hits = 0;
  for (let y = y0; y <= y1; y++) {
    const row = y * frame.width;
    for (let x = x0; x <= x1; x++) {
      const idx = (row + x) * 4;
      total++;
      const hsv = rgbToHsv(frame.data[idx]!, frame.data[idx + 1]!, frame.data[idx + 2]!);
      if (matchesPartProfile(hsv, profile)) hits++;
    }
  }
  return total === 0 ? 0 : hits / total;
}

export function circlePixelFraction(
  frame: FrameBuffer,
  cxNorm: number,
  cyNorm: number,
  rNorm: number,
  profile: PartProfile,
): number {
  const cx = cxNorm * frame.width;
  const cy = cyNorm * frame.height;
  const r = rNorm * Math.min(frame.width, frame.height);
  const r2 = r * r;
  const x0 = Math.max(0, Math.floor(cx - r));
  const y0 = Math.max(0, Math.floor(cy - r));
  const x1 = Math.min(frame.width - 1, Math.ceil(cx + r));
  const y1 = Math.min(frame.height - 1, Math.ceil(cy + r));
  let total = 0;
  let hits = 0;
  for (let y = y0; y <= y1; y++) {
    const dy = y - cy;
    const row = y * frame.width;
    for (let x = x0; x <= x1; x++) {
      const dx = x - cx;
      if (dx * dx + dy * dy > r2) continue;
      const idx = (row + x) * 4;
      total++;
      const hsv = rgbToHsv(frame.data[idx]!, frame.data[idx + 1]!, frame.data[idx + 2]!);
      if (matchesPartProfile(hsv, profile)) hits++;
    }
  }
  return total === 0 ? 0 : hits / total;
}
