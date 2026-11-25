"""Step verification endpoint POST /v1/sessions/{id}/verify (BUILD_PLAN 12.2 & 18)."""

from __future__ import annotations

import base64
from uuid import UUID

from fastapi import APIRouter, Depends

from parampara.agents.verifier.agent import verify_step
from parampara.api.deps import CurrentUser, get_current_user
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import resolve_database_url
from parampara.db.repos.sessions import SessionRecord, get_session_record, record_server_vlm_key
from parampara.db.repos.sessions_db import insert_step_events_db, load_session_db
from parampara.domain.generated import (
    Scope4,
    Status3,
    Step,
    StepEvent,
    Type,
    VerifierVerdict,
    VerifyRequest,
)
from parampara.tools.hashing import sha256_bytes
from parampara.tools.storage import download_bytes, upload_bytes

router = APIRouter(prefix="/v1")
MAX_VERIFY_FRAME_BYTES = 600 * 1024


def _decode_frame(frame_jpeg_b64: str) -> bytes:
    try:
        raw = base64.b64decode(frame_jpeg_b64, validate=True)
    except Exception as exc:
        raise AppError(
            status_code=400, code="invalid_frame", message="Invalid base64 JPEG"
        ) from exc
    if len(raw) > MAX_VERIFY_FRAME_BYTES:
        raise AppError(
            status_code=413, code="frame_too_large", message="Frame exceeds 600 KB limit"
        )
    return raw


async def _store_and_load_ref(
    settings: Settings, session_id: UUID, step: Step, frame_bytes: bytes
) -> bytes | None:
    frame_hash = sha256_bytes(frame_bytes)
    await upload_bytes(
        supabase_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket="frames",
        path=f"{session_id}/{step.id}/{frame_hash[:16]}.jpg",
        data=frame_bytes,
        content_type="image/jpeg",
    )
    if not step.reference_keyframe:
        return None
    ref_path = f"keyframes/{step.reference_keyframe.clip_id}/{step.id}.jpg"
    return await download_bytes(
        supabase_url=settings.supabase_url,
        service_key=settings.supabase_service_role_key,
        bucket="frames",
        path=ref_path,
    )


async def _record_vlm_pass(
    url: str, ses: SessionRecord, step_id: str, frame_t_ms: int, verdict: VerifierVerdict
) -> None:
    ev = StepEvent(
        session_id=ses.id,
        step_id=step_id,
        type=Type.vlm_key,
        t_ms=frame_t_ms,
        payload={"confidence": verdict.confidence, "model": verdict.model},
        frame_sha256=verdict.frame_sha256,
    )
    if url:
        await insert_step_events_db(url, ses.id, [ev], server_verified=True)
    else:
        record_server_vlm_key(ses, step_id, frame_t_ms)
        ses.events.append(ev)


@router.post(
    "/sessions/{session_id}/verify",
    response_model=VerifierVerdict,
    response_model_by_alias=True,
)
async def verify_session_step(
    session_id: UUID,
    body: VerifyRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> VerifierVerdict:
    url = resolve_database_url(settings.database_url)
    ses = await load_session_db(url, session_id) if url else get_session_record(session_id)
    if ses is None or ses.trainee_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    step = next((s for s in ses.graph.steps if s.id == body.step_id), None)
    if step is None:
        raise AppError(status_code=400, code="unknown_step", message=f"Unknown step {body.step_id}")
    frame_bytes = _decode_frame(body.frame_jpeg_b64)
    ref_bytes = await _store_and_load_ref(settings, session_id, step, frame_bytes)
    verdict = await verify_step(
        step=step,
        req=body,
        frame_bytes=frame_bytes,
        ref_frame_bytes=ref_bytes,
        scope=Scope4(session_id=session_id),
        settings=settings,
    )
    if verdict.status == Status3.pass_ and verdict.confidence >= 0.7:
        await _record_vlm_pass(url, ses, step.id, body.frame_t_ms, verdict)
    return verdict
