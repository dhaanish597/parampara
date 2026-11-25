/**
 * Pure zone and part colour calibration helpers (BUILD_PLAN 17.3).
 */

import type { PartProfile, ZoneCalibration } from "@parampara/contracts";
import {
  rectPixelFraction,
  rgbToHsv,
  type FrameBuffer,
  type HsvColor,
} from "./colour.js";

const DEFAULT_ZONE_RADIUS = 0.06;
const MIN_ZONE_RADIUS = 0.03;
const MAX_ZONE_RADIUS = 0.12;
const OVERLAP_THRESHOLD = 0.2;

export interface OverlapResult {
  readonly ok: boolean;
  readonly overlaps: ReadonlyArray<{
    readonly a: string;
    readonly b: string;
    readonly fraction: number;
  }>;
}

export function buildZoneCalibration(
  zoneId: string,
  x: number,
  y: number,
  radius = DEFAULT_ZONE_RADIUS,
): ZoneCalibration {
  const clampedR = Math.max(MIN_ZONE_RADIUS, Math.min(MAX_ZONE_RADIUS, radius));
  return {
    zone_id: zoneId,
    x: Math.max(0, Math.min(1, x)),
    y: Math.max(0, Math.min(1, y)),
    radius: clampedR,
  };
}

function median(values: number[]): number {
  if (values.length === 0) return 0;
  const sorted = [...values].sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  return sorted.length % 2 === 1 ? sorted[mid]! : (sorted[mid - 1]! + sorted[mid]!) / 2;
}

function circularMedianHue(hues: number[]): number {
  if (hues.length === 0) return 0;
  let sinSum = 0;
  let cosSum = 0;
  for (const h of hues) {
    const rad = (h * Math.PI) / 180;
    sinSum += Math.sin(rad);
    cosSum += Math.cos(rad);
  }
  const deg = (Math.atan2(sinSum, cosSum) * 180) / Math.PI;
  return deg < 0 ? deg + 360 : deg;
}

function sampleCentreBox(frames: readonly FrameBuffer[]): HsvColor[] {
  const pixels: HsvColor[] = [];
  for (const frame of frames) {
    const x0 = Math.floor(frame.width * 0.4);
    const x1 = Math.ceil(frame.width * 0.6);
    const y0 = Math.floor(frame.height * 0.4);
    const y1 = Math.ceil(frame.height * 0.6);
    for (let y = y0; y < y1; y++) {
      const row = y * frame.width;
      for (let x = x0; x < x1; x++) {
        const idx = (row + x) * 4;
        pixels.push(rgbToHsv(frame.data[idx]!, frame.data[idx + 1]!, frame.data[idx + 2]!));
      }
    }
  }
  return pixels;
}

export function buildPartProfile(
  partId: string,
  samples: readonly FrameBuffer[],
): PartProfile {
  const all = sampleCentreBox(samples);
  const medVAll = median(all.map((p) => p.v));
  const dark = medVAll < 0.25;
  const filtered = dark ? all : all.filter((p) => p.s >= 0.15);
  const usable = filtered.length > 0 ? filtered : all;
  const medH = circularMedianHue(usable.map((p) => p.h));
  const medS = median(usable.map((p) => p.s));
  const medV = median(usable.map((p) => p.v));
  if (dark) {
    return {
      part_id: partId,
      h_deg: 0,
      s: medS,
      v: medV,
      tol_h_deg: 18,
      min_s: 0,
      min_v: 0,
      max_v: Math.min(1, medV + 0.12),
      dark: true,
    };
  }
  return {
    part_id: partId,
    h_deg: medH,
    s: medS,
    v: medV,
    tol_h_deg: 18,
    min_s: Math.max(0.25, medS - 0.2),
    min_v: Math.max(0, medV - 0.3),
    max_v: Math.min(1, medV + 0.3),
    dark: false,
  };
}

export function checkProfileOverlap(
  items: ReadonlyArray<{ readonly profile: PartProfile; readonly samples: readonly FrameBuffer[] }>,
): OverlapResult {
  const overlaps: Array<{ a: string; b: string; fraction: number }> = [];
  for (let i = 0; i < items.length; i++) {
    for (let j = 0; j < items.length; j++) {
      if (i === j) continue;
      const sampleList = items[i]!.samples;
      if (sampleList.length === 0) continue;
      let sum = 0;
      for (const frame of sampleList) {
        sum += rectPixelFraction(frame, 0.4, 0.4, 0.6, 0.6, items[j]!.profile);
      }
      const fraction = sum / sampleList.length;
      if (fraction > OVERLAP_THRESHOLD) {
        overlaps.push({ a: items[i]!.profile.part_id, b: items[j]!.profile.part_id, fraction });
      }
    }
  }
  return { ok: overlaps.length === 0, overlaps };
}
