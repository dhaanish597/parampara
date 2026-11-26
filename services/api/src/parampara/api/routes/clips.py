"""Clip upload and finalize routes (BUILD_PLAN 11.4, 12.2, T-023)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from parampara.api.deps import CurrentUser, get_current_user, require_role
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.jobs import enqueue_job
from parampara.db.pool import resolve_database_url
from parampara.db.repos.clips import (
    ClipRecord,
    create_clip_db,
    get_clip_db,
    record_clip_client_metadata_db,
)
from parampara.tools.storage import create_signed_upload_url

router = APIRouter(prefix="/v1")

ALLOWED_CLIP_MIMES = {"video/webm", "video/mp4", "video/quicktime"}


class CreateClipRequest(BaseModel):
    org_id: UUID
    kind: Literal["demo", "session"] = "demo"
    mime: str = "video/webm"


class CreateClipResponse(BaseModel):
    clip_id: UUID
    storage_path: str
    signed_url: str
    expires_at: datetime


class FinalizeClipRequest(BaseModel):
    blurred: bool
    duration_ms: int | None = Field(default=None, ge=0)
    width: int | None = Field(default=None, ge=1)
    height: int | None = Field(default=None, ge=1)
    fps: float | None = Field(default=None, gt=0)


class ClipResponse(BaseModel):
    id: UUID
    org_id: UUID
    owner_user_id: UUID
    kind: str
    storage_path: str
    mime: str
    sha256: str | None = None
    bytes: int | None = None
    duration_ms: int | None = None
    width: int | None = None
    height: int | None = None
    fps: float | None = None
    blurred: bool
    finalized_at: datetime | None = None
    job_id: UUID | None = None


def _to_response(rec: ClipRecord, *, job_id: UUID | None = None) -> ClipResponse:
    return ClipResponse(
        id=rec.id,
        org_id=rec.org_id,
        owner_user_id=rec.owner_user_id,
        kind=rec.kind,
        storage_path=rec.storage_path,
        mime=rec.mime,
        sha256=rec.sha256,
        bytes=rec.bytes,
        duration_ms=rec.duration_ms,
        width=rec.width,
        height=rec.height,
        fps=rec.fps,
        blurred=rec.blurred,
        finalized_at=rec.finalized_at,
        job_id=job_id,
    )


@router.post("/clips", response_model=CreateClipResponse)
async def create_clip(
    body: CreateClipRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CreateClipResponse:
    require_role(user, body.org_id, {"master", "trainee", "owner", "supervisor"})
    base_mime = body.mime.split(";", 1)[0].strip().lower()
    if base_mime not in ALLOWED_CLIP_MIMES:
        raise AppError(status_code=400, code="invalid_mime", message="Unsupported clip MIME type")
    db_url = resolve_database_url(settings.database_url)
    if not db_url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    clip = await create_clip_db(
        db_url,
        org_id=body.org_id,
        owner_user_id=user.user_id,
        kind=body.kind,
        mime=base_mime,
    )
    signed = await create_signed_upload_url(
        supabase_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket="clips",
        path=clip.storage_path,
    )
    upload_url = signed or f"{settings.public_web_origin}/api/local-upload/{clip.id}"
    return CreateClipResponse(
        clip_id=clip.id,
        storage_path=clip.storage_path,
        signed_url=upload_url,
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )


@router.post("/clips/{clip_id}/finalize", response_model=ClipResponse)
async def finalize_clip(
    clip_id: UUID,
    body: FinalizeClipRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ClipResponse:
    if not body.blurred:
        raise AppError(
            status_code=400,
            code="unblurred_clip",
            message="Clips must be face-blurred on device before finalize",
        )
    db_url = resolve_database_url(settings.database_url)
    if not db_url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    clip = await get_clip_db(db_url, clip_id)
    if clip is None or clip.owner_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Clip not found")
    updated = await record_clip_client_metadata_db(
        db_url,
        clip_id=clip_id,
        blurred=True,
        duration_ms=body.duration_ms,
        width=body.width,
        height=body.height,
        fps=body.fps,
    )
    if updated is None:
        raise AppError(status_code=404, code="not_found", message="Clip not found")
    job_id = await enqueue_job(db_url, kind="finalize_clip", payload={"clip_id": str(clip_id)})
    return _to_response(updated, job_id=job_id)


@router.get("/clips/{clip_id}", response_model=ClipResponse)
async def get_clip(
    clip_id: UUID,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ClipResponse:
    db_url = resolve_database_url(settings.database_url)
    if not db_url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    clip = await get_clip_db(db_url, clip_id)
    if clip is None:
        raise AppError(status_code=404, code="not_found", message="Clip not found")
    if clip.owner_user_id != user.user_id:
        require_role(user, clip.org_id, {"owner", "supervisor"})
    return _to_response(clip)
