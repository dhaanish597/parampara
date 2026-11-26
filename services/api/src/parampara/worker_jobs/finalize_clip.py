"""Exemplar job handler: finalize_clip (BUILD_PLAN 12.3, 31.4, T-023).

Downloads an uploaded clip from Supabase Storage (`clips` bucket), computes its
SHA-256 server-side, transcodes webm -> mp4 with ffmpeg, probes video metadata
with ffprobe, uploads the mp4, and marks the clip finalized. Idempotent: if the
clip is already finalized with a SHA-256, returns immediately without re-running.
"""

from __future__ import annotations

import asyncio
import json
import subprocess
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

from parampara.api.settings import Settings
from parampara.db.pool import resolve_database_url
from parampara.db.repos.clips import ClipRecord, get_clip_db, save_clip_finalized_db
from parampara.domain.generated import Kind4, Scope4
from parampara.telemetry.recorder import get_telemetry_bus
from parampara.tools.hashing import sha256_bytes
from parampara.tools.storage import download_bytes, upload_bytes


@dataclass(frozen=True)
class VideoMetadata:
    duration_ms: int
    width: int
    height: int
    fps: float


def _parse_fps(rate_str: str) -> float:
    if "/" in rate_str:
        num_s, den_s = rate_str.split("/", 1)
        num, den = float(num_s), float(den_s)
        return round(num / den, 2) if den > 0 else 0.0
    return round(float(rate_str), 2) if rate_str else 0.0


def probe_video_metadata(video_path: Path) -> VideoMetadata:
    """Run ffprobe on a local video file and extract duration, dimensions, and fps."""
    cmd = [
        "ffprobe",
        "-v",
        "error",
        "-select_streams",
        "v:0",
        "-show_entries",
        "stream=width,height,r_frame_rate:format=duration",
        "-of",
        "json",
        str(video_path),
    ]
    proc = subprocess.run(cmd, check=True, capture_output=True, text=True)  # noqa: S603
    data = json.loads(proc.stdout)
    streams = data.get("streams") or []
    if not streams:
        raise RuntimeError(f"ffprobe found no video stream in {video_path.name}")
    stream = streams[0]
    dur_s = float((data.get("format") or {}).get("duration") or 0.0)
    return VideoMetadata(
        duration_ms=max(1, int(round(dur_s * 1000))),
        width=int(stream.get("width") or 0),
        height=int(stream.get("height") or 0),
        fps=_parse_fps(str(stream.get("r_frame_rate") or "0")),
    )


def transcode_to_mp4(src_path: Path, dst_path: Path) -> None:
    """Transcode an input video (e.g. webm) to H.264/AAC MP4 with faststart."""
    cmd = [
        "ffmpeg",
        "-y",
        "-i",
        str(src_path),
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-pix_fmt",
        "yuv420p",
        "-c:a",
        "aac",
        "-movflags",
        "+faststart",
        str(dst_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603


def _transcode_and_probe_bytes(raw_bytes: bytes, mime: str) -> tuple[bytes, VideoMetadata]:
    """Transcode raw clip bytes to MP4 (if needed) and probe final metadata."""
    src_ext = ".mp4" if "mp4" in mime.lower() else ".webm"
    with tempfile.TemporaryDirectory(prefix="parampara_clip_") as td:
        tmp = Path(td)
        src_file = tmp / f"input{src_ext}"
        src_file.write_bytes(raw_bytes)
        if src_ext == ".mp4":
            out_file = src_file
        else:
            out_file = tmp / "output.mp4"
            transcode_to_mp4(src_file, out_file)
        meta = probe_video_metadata(out_file)
        return out_file.read_bytes(), meta


def _mp4_storage_path(clip: ClipRecord) -> str:
    base = clip.storage_path.rsplit(".", 1)[0]
    return f"{base}.mp4"


async def _process_and_upload_clip(
    db_url: str, clip: ClipRecord, settings: Settings
) -> tuple[str, str, int, VideoMetadata]:
    raw = await download_bytes(
        supabase_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket="clips",
        path=clip.storage_path,
    )
    if not raw:
        raise RuntimeError(f"Uploaded object missing in clips/{clip.storage_path}")
    mp4_bytes, meta = await asyncio.to_thread(_transcode_and_probe_bytes, raw, clip.mime)
    digest = sha256_bytes(mp4_bytes)
    mp4_path = _mp4_storage_path(clip)
    uploaded = await upload_bytes(
        supabase_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket="clips",
        path=mp4_path,
        data=mp4_bytes,
        content_type="video/mp4",
    )
    if not uploaded:
        raise RuntimeError(f"Failed to upload transcoded clip to clips/{mp4_path}")
    await save_clip_finalized_db(
        db_url,
        clip_id=clip.id,
        storage_path=mp4_path,
        mime="video/mp4",
        sha256=digest,
        byte_count=len(mp4_bytes),
        duration_ms=meta.duration_ms,
        width=meta.width,
        height=meta.height,
        fps=meta.fps,
    )
    return mp4_path, digest, len(mp4_bytes), meta


async def handle_finalize_clip(payload: dict[str, Any], settings: Settings) -> dict[str, Any]:
    """Finalize a clip: idempotency check, download, transcode, hash, probe, upload, persist."""
    clip_id, t0, bus = UUID(str(payload["clip_id"])), time.perf_counter(), get_telemetry_bus()
    bus.record_trace(
        agent="worker", kind=Kind4.agent_start, summary=f"finalize_clip {clip_id}", scope=Scope4()
    )
    db_url = resolve_database_url(settings.database_url)
    if not db_url:
        raise RuntimeError("DATABASE_URL is required for finalize_clip")
    clip = await get_clip_db(db_url, clip_id)
    if clip is None:
        raise RuntimeError(f"Clip {clip_id} not found")
    if clip.finalized_at is not None and clip.sha256:
        bus.record_trace(
            agent="worker",
            kind=Kind4.agent_end,
            summary=f"finalize_clip skipped (already done) {clip_id}",
            scope=Scope4(),
            latency_ms=int((time.perf_counter() - t0) * 1000),
        )
        return {"clip_id": str(clip_id), "sha256": clip.sha256, "skipped": True}
    mp4_path, digest, nbytes, meta = await _process_and_upload_clip(db_url, clip, settings)
    summary = f"finalize_clip done {clip_id} ({meta.width}x{meta.height}, {meta.duration_ms}ms)"
    bus.record_trace(
        agent="worker",
        kind=Kind4.agent_end,
        summary=summary,
        scope=Scope4(),
        latency_ms=int((time.perf_counter() - t0) * 1000),
    )
    return {
        "clip_id": str(clip_id),
        "storage_path": mp4_path,
        "sha256": digest,
        "bytes": nbytes,
        "duration_ms": meta.duration_ms,
    }
