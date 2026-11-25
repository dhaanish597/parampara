"""Tests for ffmpeg keyframe extraction tool (BUILD_PLAN 14.2)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

from parampara.tools.keyframes import extract_keyframes


def make_test_video(path: Path, duration_s: int = 3) -> None:
    ffmpeg = shutil.which("ffmpeg")
    assert ffmpeg is not None, "ffmpeg must be installed"
    subprocess.run(  # noqa: S603
        [
            ffmpeg,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"testsrc=duration={duration_s}:size=320x180:rate=10",
            "-pix_fmt",
            "yuv420p",
            str(path),
        ],
        check=True,
        capture_output=True,
    )


def test_extract_keyframes_at_end_ms_minus_300(tmp_path: Path) -> None:
    video = tmp_path / "demo.mp4"
    out_dir = tmp_path / "frames"
    make_test_video(video, duration_s=3)

    extracted = extract_keyframes(
        video_path=video,
        segments=[("s1", 0, 1200), ("s2", 1200, 2600)],
        out_dir=out_dir,
    )
    assert set(extracted.keys()) == {"s1", "s2"}
    for step_id, frame in extracted.items():
        assert frame.path.exists()
        assert frame.path.stat().st_size > 100
        assert frame.path.read_bytes()[:2] == b"\xff\xd8"
        if step_id == "s1":
            assert frame.ts_ms == 900
        else:
            assert frame.ts_ms == 2300
