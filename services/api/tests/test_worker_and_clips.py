"""Tests for clip upload/finalize pipeline and Postgres job worker (BUILD_PLAN 12.2-12.3, T-023)."""

from __future__ import annotations

import asyncio
import subprocess
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from parampara.api.deps import ALL_DEMO_ROLES, CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.settings import DEFAULT_DEMO_ORG_ID, Settings, get_settings
from parampara.db.jobs import (
    backoff_seconds_for_attempt,
    claim_next_job,
    enqueue_job,
    get_job,
)
from parampara.db.repos.clips import get_clip_db
from parampara.worker import WorkerRunner
from parampara.worker_jobs.finalize_clip import (
    handle_finalize_clip,
    probe_video_metadata,
    transcode_to_mp4,
)

RAMESH_ID = UUID("20000000-0000-4000-8000-000000000001")


def _db_reachable(db_url: str) -> bool:
    if not db_url:
        return False
    try:
        with psycopg.connect(db_url, connect_timeout=1) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def _generate_test_webm(out_path: Path) -> bytes:
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        "testsrc=duration=1:size=320x180:rate=15",
        "-f",
        "lavfi",
        "-i",
        "anullsrc=r=16000:cl=mono",
        "-t",
        "1",
        "-c:v",
        "libvpx",
        "-c:a",
        "libopus",
        str(out_path),
    ]
    subprocess.run(cmd, check=True, capture_output=True)  # noqa: S603
    return out_path.read_bytes()


def test_backoff_schedule_and_real_ffmpeg_transcode_probe(tmp_path: Path) -> None:
    assert backoff_seconds_for_attempt(1) == 5
    assert backoff_seconds_for_attempt(2) == 30
    assert backoff_seconds_for_attempt(3) == 120
    webm_path = tmp_path / "sample.webm"
    mp4_path = tmp_path / "sample.mp4"
    _generate_test_webm(webm_path)
    transcode_to_mp4(webm_path, mp4_path)
    meta = probe_video_metadata(mp4_path)
    assert meta.width == 320 and meta.height == 180
    assert 800 <= meta.duration_ms <= 1400 and meta.fps > 0


async def test_worker_skip_locked_and_concurrency_cap() -> None:
    settings = Settings()
    if not _db_reachable(settings.database_url):
        pytest.skip("Local Supabase Postgres not reachable")
    kind = f"test_fake_{uuid4().hex[:8]}"
    ids = [await enqueue_job(settings.database_url, kind=kind, payload={"n": i}) for i in (1, 2, 3)]
    active, peak, done_ids = 0, 0, []

    async def slow_handler(payload: dict[str, Any], _s: Settings) -> dict[str, Any]:
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.08)
        done_ids.append(payload["n"])
        active -= 1
        return {"ok": True}

    runner = WorkerRunner(settings, handlers={kind: slow_handler}, max_concurrency=2)
    assert await runner.poll_once(kinds=[kind]) == 2
    await runner.drain()
    assert peak == 2 and await runner.poll_once(kinds=[kind]) == 1
    await runner.drain()
    assert sorted(done_ids) == [1, 2, 3]
    for jid in ids:
        rec = await get_job(settings.database_url, jid)
        assert rec is not None and rec.status == "done"


async def test_worker_retries_three_times_and_records_last_error() -> None:
    settings = Settings()
    if not _db_reachable(settings.database_url):
        pytest.skip("Local Supabase Postgres not reachable")
    fail_kind = f"test_fail_{uuid4().hex[:8]}"
    fj = await enqueue_job(settings.database_url, kind=fail_kind, payload={})

    async def broken_handler(_p: dict[str, Any], _s: Settings) -> dict[str, Any]:
        raise ValueError("boom-retry")

    f_runner = WorkerRunner(settings, handlers={fail_kind: broken_handler}, max_attempts=3)
    for expected_status in ("queued", "queued", "failed"):
        with psycopg.connect(settings.database_url, autocommit=True) as conn:
            conn.execute(
                "UPDATE jobs SET run_after = now() - interval '1 second' WHERE id = %s",
                (fj,),
            )
        claimed = await claim_next_job(settings.database_url, kinds=[fail_kind])
        assert claimed is not None
        assert await f_runner.execute_job(claimed) == expected_status
    final_rec = await get_job(settings.database_url, fj)
    assert final_rec is not None and final_rec.status == "failed" and final_rec.attempts == 3
    assert final_rec.last_error and "boom-retry" in final_rec.last_error


def _clip_test_app(settings: Settings) -> Any:
    app = create_app()
    user = CurrentUser(
        user_id=RAMESH_ID,
        display_name="Ramesh (demo)",
        pseudonym="ramesh_master",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_current_user] = lambda: user
    return app


async def test_real_clip_upload_finalize_worker_and_idempotency(tmp_path: Path) -> None:
    settings = Settings()
    if not _db_reachable(settings.database_url) or not (
        settings.supabase_url and settings.supabase_service_role_key
    ):
        pytest.skip("Local Supabase Postgres or Storage env not configured")
    webm_bytes = _generate_test_webm(tmp_path / "demo.webm")
    app = _clip_test_app(settings)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        created = await c.post(
            "/v1/clips",
            json={"org_id": DEFAULT_DEMO_ORG_ID, "kind": "demo", "mime": "video/webm"},
        )
        assert created.status_code == 200
        body = created.json()
        clip_id = UUID(body["clip_id"])
        async with httpx.AsyncClient(timeout=15.0) as storage_client:
            up = await storage_client.put(
                body["signed_url"], content=webm_bytes, headers={"Content-Type": "video/webm"}
            )
            assert up.status_code in (200, 201)
        bad = await c.post(f"/v1/clips/{clip_id}/finalize", json={"blurred": False})
        assert bad.status_code == 400 and bad.json()["error"]["code"] == "unblurred_clip"
        fin = await c.post(
            f"/v1/clips/{clip_id}/finalize",
            json={"blurred": True, "duration_ms": 1000, "width": 320, "height": 180, "fps": 15.0},
        )
        assert fin.status_code == 200 and fin.json()["job_id"]
    runner = WorkerRunner(settings)
    assert await runner.poll_once(kinds=["finalize_clip"]) >= 1
    await runner.drain()
    clip = await get_clip_db(settings.database_url, clip_id)
    assert clip is not None and clip.finalized_at is not None and clip.sha256
    assert len(clip.sha256) == 64 and clip.mime == "video/mp4" and clip.width == 320
    second = await handle_finalize_clip({"clip_id": str(clip_id)}, settings)
    assert second["skipped"] is True and second["sha256"] == clip.sha256
