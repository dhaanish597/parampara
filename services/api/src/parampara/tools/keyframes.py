"""Deterministic ffmpeg keyframe extractor for Skill Compiler (BUILD_PLAN 14.2)."""

from __future__ import annotations

import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ExtractedKeyframe:
    step_id: str
    ts_ms: int
    path: Path


def _target_ts_ms(start_ms: int, end_ms: int) -> int:
    candidate = end_ms - 300
    return max(start_ms, max(0, candidate))


def extract_keyframes(
    *,
    video_path: Path,
    segments: list[tuple[str, int, int]],
    out_dir: Path,
) -> dict[str, ExtractedKeyframe]:
    """Extract one JPEG keyframe at end_ms - 300 for each (step_id, start_ms, end_ms)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        raise RuntimeError("ffmpeg binary not found on PATH")
    if not video_path.exists():
        raise FileNotFoundError(f"Video not found: {video_path}")

    out_dir.mkdir(parents=True, exist_ok=True)
    result: dict[str, ExtractedKeyframe] = {}
    for step_id, start_ms, end_ms in segments:
        if not step_id or "/" in step_id or "\\" in step_id or ".." in step_id:
            raise ValueError(f"Invalid step_id for keyframe output: {step_id!r}")
        ts_ms = _target_ts_ms(start_ms, end_ms)
        out_file = (out_dir / f"{step_id}.jpg").resolve()
        if out_dir.resolve() not in out_file.parents:
            raise ValueError(f"Path traversal blocked for step_id: {step_id!r}")
        cmd = [
            ffmpeg,
            "-y",
            "-ss",
            f"{ts_ms / 1000.0:.3f}",
            "-i",
            str(video_path),
            "-frames:v",
            "1",
            "-q:v",
            "2",
            str(out_file),
        ]
        subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
        result[step_id] = ExtractedKeyframe(step_id=step_id, ts_ms=ts_ms, path=out_file)
    return result
