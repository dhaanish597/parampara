"""PostgreSQL repository for clips table (BUILD_PLAN 11.1, 11.4, 12.2, T-023)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.db.pool import open_db


@dataclass(frozen=True)
class ClipRecord:
    id: UUID
    org_id: UUID
    owner_user_id: UUID
    kind: str
    storage_path: str
    mime: str
    sha256: str | None
    bytes: int | None
    duration_ms: int | None
    width: int | None
    height: int | None
    fps: float | None
    blurred: bool
    finalized_at: datetime | None
    created_at: datetime


def _row_to_clip(row: dict[str, Any]) -> ClipRecord:
    return ClipRecord(
        id=UUID(str(row["id"])),
        org_id=UUID(str(row["org_id"])),
        owner_user_id=UUID(str(row["owner_user_id"])),
        kind=str(row["kind"]),
        storage_path=str(row["storage_path"]),
        mime=str(row["mime"]),
        sha256=str(row["sha256"]) if row["sha256"] is not None else None,
        bytes=int(row["bytes"]) if row["bytes"] is not None else None,
        duration_ms=int(row["duration_ms"]) if row["duration_ms"] is not None else None,
        width=int(row["width"]) if row["width"] is not None else None,
        height=int(row["height"]) if row["height"] is not None else None,
        fps=float(row["fps"]) if row["fps"] is not None else None,
        blurred=bool(row["blurred"]),
        finalized_at=row["finalized_at"],
        created_at=row["created_at"],
    )


def build_clip_storage_path(org_id: UUID, clip_id: UUID, mime: str) -> str:
    """Server-generated storage path under clips bucket (BUILD_PLAN 11.4)."""
    ext = "mp4" if "mp4" in mime.lower() else "webm"
    return f"org/{org_id}/clips/{clip_id}.{ext}"


async def create_clip_db(
    database_url: str,
    *,
    org_id: UUID,
    owner_user_id: UUID,
    kind: str,
    mime: str,
) -> ClipRecord:
    clip_id = uuid4()
    storage_path = build_clip_storage_path(org_id, clip_id, mime)
    sql = (
        "INSERT INTO clips (id, org_id, owner_user_id, kind, storage_path, mime) "
        "VALUES (%s, %s, %s, %s::clip_kind, %s, %s) "
        "RETURNING id, org_id, owner_user_id, kind::text AS kind, storage_path, mime, "
        "sha256, bytes, duration_ms, width, height, fps, blurred, finalized_at, created_at"
    )
    async with open_db(database_url) as conn, conn.transaction():
        row = await (
            await conn.execute(sql, (clip_id, org_id, owner_user_id, kind, storage_path, mime))
        ).fetchone()
    if row is None:
        raise RuntimeError("Failed to insert clip row")
    return _row_to_clip(dict(row))


async def get_clip_db(database_url: str, clip_id: UUID) -> ClipRecord | None:
    sql = (
        "SELECT id, org_id, owner_user_id, kind::text AS kind, storage_path, mime, "
        "sha256, bytes, duration_ms, width, height, fps, blurred, finalized_at, created_at "
        "FROM clips WHERE id = %s"
    )
    async with open_db(database_url) as conn:
        row = await (await conn.execute(sql, (clip_id,))).fetchone()
    return _row_to_clip(dict(row)) if row else None


async def record_clip_client_metadata_db(
    database_url: str,
    *,
    clip_id: UUID,
    blurred: bool,
    duration_ms: int | None,
    width: int | None,
    height: int | None,
    fps: float | None,
) -> ClipRecord | None:
    sql = (
        "UPDATE clips SET blurred = %s, "
        "duration_ms = COALESCE(duration_ms, %s), "
        "width = COALESCE(width, %s), "
        "height = COALESCE(height, %s), "
        "fps = COALESCE(fps, %s) WHERE id = %s "
        "RETURNING id, org_id, owner_user_id, kind::text AS kind, storage_path, mime, "
        "sha256, bytes, duration_ms, width, height, fps, blurred, finalized_at, created_at"
    )
    async with open_db(database_url) as conn, conn.transaction():
        row = await (
            await conn.execute(sql, (blurred, duration_ms, width, height, fps, clip_id))
        ).fetchone()
    return _row_to_clip(dict(row)) if row else None


async def save_clip_finalized_db(
    database_url: str,
    *,
    clip_id: UUID,
    storage_path: str,
    mime: str,
    sha256: str,
    byte_count: int,
    duration_ms: int,
    width: int,
    height: int,
    fps: float,
) -> ClipRecord | None:
    sql = (
        "UPDATE clips SET storage_path = %s, mime = %s, sha256 = %s, bytes = %s, "
        "duration_ms = %s, width = %s, height = %s, fps = %s, finalized_at = now() WHERE id = %s "
        "RETURNING id, org_id, owner_user_id, kind::text AS kind, storage_path, mime, "
        "sha256, bytes, duration_ms, width, height, fps, blurred, finalized_at, created_at"
    )
    params = (storage_path, mime, sha256, byte_count, duration_ms, width, height, fps, clip_id)
    async with open_db(database_url) as conn, conn.transaction():
        row = await (await conn.execute(sql, params)).fetchone()
    return _row_to_clip(dict(row)) if row else None
