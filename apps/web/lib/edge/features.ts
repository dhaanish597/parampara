/**
 * Pure per-frame feature extraction (BUILD_PLAN 17.2).
 */

import type { Calibration, PartProfile, ZoneCalibration } from "@parampara/contracts";
import { circlePixelFraction, rectPixelFraction, type FrameBuffer } from "./colour.js";

export interface HandLandmark {
  readonly x: number;
  readonly y: number;
  readonly z: number;
}

export interface HandInput {
  readonly landmarks: readonly HandLandmark[];
  readonly handedness: "Left" | "Right";
}

export interface BoundingBox {
  readonly minX: number;
  readonly minY: number;
  readonly maxX: number;
  readonly maxY: number;
}

export interface HandFeatures {
  readonly handedness: "Left" | "Right";
  readonly pinch_point: { readonly x: number; readonly y: number };
  readonly pinching: boolean;
  readonly box: BoundingBox;
  readonly held_part: string | null;
  readonly landmarks: readonly HandLandmark[];
}

export interface FrameFeatures {
  readonly t_ms: number;
  readonly hands: readonly HandFeatures[];
  readonly zone_part_fraction: Record<string, Record<string, number>>;
  readonly hand_in_zone: Record<string, boolean>;
  readonly motion: number;
}

export interface ExtractInput {
  readonly t_ms: number;
  readonly frame: FrameBuffer;
  readonly hands: readonly HandInput[];
  readonly calibration: Calibration;
  readonly prev?: FrameFeatures;
}

const PINCH_DIST_THRESHOLD = 0.08;
const HELD_PART_MIN_FRACTION = 0.03;

function pixelDistNorm(
  ax: number,
  ay: number,
  bx: number,
  by: number,
  w: number,
  h: number,
): number {
  const minDim = Math.max(1, Math.min(w, h));
  return Math.hypot((ax - bx) * w, (ay - by) * h) / minDim;
}

function computeHandBox(landmarks: readonly HandLandmark[]): BoundingBox {
  let minX = 1;
  let minY = 1;
  let maxX = 0;
  let maxY = 0;
  for (const lm of landmarks) {
    if (lm.x < minX) minX = lm.x;
    if (lm.y < minY) minY = lm.y;
    if (lm.x > maxX) maxX = lm.x;
    if (lm.y > maxY) maxY = lm.y;
  }
  const padX = (maxX - minX) * 0.2;
  const padY = (maxY - minY) * 0.2;
  return {
    minX: Math.max(0, minX - padX),
    minY: Math.max(0, minY - padY),
    maxX: Math.min(1, maxX + padX),
    maxY: Math.min(1, maxY + padY),
  };
}

function detectHeldPart(
  frame: FrameBuffer,
  box: BoundingBox,
  parts: readonly PartProfile[],
): string | null {
  let bestPart: string | null = null;
  let bestFrac = HELD_PART_MIN_FRACTION;
  for (const part of parts) {
    const frac = rectPixelFraction(frame, box.minX, box.minY, box.maxX, box.maxY, part);
    if (frac >= bestFrac) {
      bestFrac = frac;
      bestPart = part.part_id;
    }
  }
  return bestPart;
}

function extractHand(
  hand: HandInput,
  frame: FrameBuffer,
  parts: readonly PartProfile[],
): HandFeatures {
  const thumb = hand.landmarks[4] ?? { x: 0, y: 0, z: 0 };
  const index = hand.landmarks[8] ?? { x: 0, y: 0, z: 0 };
  const dist = pixelDistNorm(thumb.x, thumb.y, index.x, index.y, frame.width, frame.height);
  const box = computeHandBox(hand.landmarks);
  return {
    handedness: hand.handedness,
    pinch_point: { x: (thumb.x + index.x) / 2, y: (thumb.y + index.y) / 2 },
    pinching: dist < PINCH_DIST_THRESHOLD,
    box,
    held_part: detectHeldPart(frame, box, parts),
    landmarks: hand.landmarks,
  };
}

function isHandInZone(
  hands: readonly HandInput[],
  zone: ZoneCalibration,
  w: number,
  h: number,
): boolean {
  for (const hand of hands) {
    for (const lm of hand.landmarks) {
      if (pixelDistNorm(lm.x, lm.y, zone.x, zone.y, w, h) <= zone.radius) return true;
    }
  }
  return false;
}

function computeMotion(
  currHands: readonly HandInput[],
  prev?: FrameFeatures,
): number {
  if (!prev || currHands.length === 0 || prev.hands.length === 0) return 0;
  const prevBySide = new Map(prev.hands.map((h) => [h.handedness, h]));
  let sum = 0;
  let count = 0;
  for (const curr of currHands) {
    const match = prevBySide.get(curr.handedness);
    if (!match) continue;
    const n = Math.min(curr.landmarks.length, match.landmarks.length);
    for (let i = 0; i < n; i++) {
      sum += Math.hypot(
        curr.landmarks[i]!.x - match.landmarks[i]!.x,
        curr.landmarks[i]!.y - match.landmarks[i]!.y,
      );
      count++;
    }
  }
  return count === 0 ? 0 : sum / count;
}

export function extractFrameFeatures(input: ExtractInput): FrameFeatures {
  const w = input.calibration.frame_w || input.frame.width;
  const h = input.calibration.frame_h || input.frame.height;
  const hands = input.hands.map((hand) => extractHand(hand, input.frame, input.calibration.parts));
  const zone_part_fraction: Record<string, Record<string, number>> = {};
  const hand_in_zone: Record<string, boolean> = {};
  for (const zone of input.calibration.zones) {
    const map: Record<string, number> = {};
    for (const part of input.calibration.parts) {
      map[part.part_id] = circlePixelFraction(input.frame, zone.x, zone.y, zone.radius, part);
    }
    zone_part_fraction[zone.zone_id] = map;
    hand_in_zone[zone.zone_id] = isHandInZone(input.hands, zone, w, h);
  }
  return {
    t_ms: input.t_ms,
    hands,
    zone_part_fraction,
    hand_in_zone,
    motion: computeMotion(input.hands, input.prev),
  };
}
