"""Session lifecycle routes: start, calibration, events, complete, get (BUILD_PLAN 12.2)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from parampara.agents.coach.builder import build_coach_system_instruction, build_live_connect_config
from parampara.agents.coach.token import mint_live_token
from parampara.api.deps import CurrentUser, get_current_user, require_role
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import open_db, resolve_database_url
from parampara.db.repos.sessions import (
    SessionRecord,
    compute_session_summary,
    finalize_mastery_and_summary,
    get_session_record,
    get_user_mastery,
    save_session,
)
from parampara.db.repos.sessions_db import (
    insert_session_db,
    insert_step_events_db,
    load_completed_runs_db,
    load_session_db,
    load_user_mastery_db,
    save_calibration_db,
    save_completion_db,
)
from parampara.db.repos.skill_versions import SkillVersionRow, get_skill_version
from parampara.domain.generated import (
    Calibration,
    Coach,
    HazardAudioItem,
    Kind4,
    Live,
    Mode,
    Scope4,
    SessionStartRequest,
    SessionStartResponse,
    SessionSummary,
    Status2,
    StepEvent,
    Type,
    Upload,
)
from parampara.telemetry.recorder import get_telemetry_bus
from parampara.tools.bkt import select_mode

router = APIRouter(prefix="/v1")


class EventsBatchRequest(BaseModel):
    events: list[StepEvent]


class SessionCompleteRequest(BaseModel):
    status: Status2 = Status2.completed
    clip_id: UUID | None = None
    coach: Coach = Coach.live
    edge_fps: float | None = None


class OkResponse(BaseModel):
    ok: bool


class EventsAcceptedResponse(BaseModel):
    accepted: int


class SessionDetailResponse(BaseModel):
    session_id: UUID
    skill_version_id: UUID
    mode: str
    status: str
    summary: SessionSummary | None = None
    events: list[StepEvent]


async def _load_session(database_url: str, session_id: UUID) -> SessionRecord | None:
    url = resolve_database_url(database_url)
    if url:
        return await load_session_db(url, session_id)
    return get_session_record(session_id)


async def _load_master_name(database_url: str, sv: SkillVersionRow) -> str:
    url = resolve_database_url(database_url)
    if not url:
        return "Master"
    sql = (
        "SELECT p.display_name FROM skill_versions sv "
        "JOIN profiles p ON p.id = sv.author_user_id WHERE sv.id = %s"
    )
    async with open_db(url) as conn:
        row = await (await conn.execute(sql, (sv.id,))).fetchone()
    return str(row["display_name"]) if row else "Master"


async def _build_start_payload(
    sv: SkillVersionRow,
    user: CurrentUser,
    master_name: str,
    mode: Mode,
    needs_help: list[str],
    token: str,
    expires_at: datetime,
    live_cfg: dict[str, Any],
    settings: Settings,
) -> SessionStartResponse:
    session_id, clip_id = uuid4(), uuid4()
    rec = SessionRecord(session_id, sv.org_id, sv.id, user.user_id, mode, sv.graph, clip_id=clip_id)
    url = resolve_database_url(settings.database_url)
    if url:
        await insert_session_db(url, rec, settings.model_live)
    else:
        save_session(rec)
    hazards = [
        HazardAudioItem(hazard_id=h.id, url=h.interrupt_audio_path or "") for h in sv.graph.hazards
    ]
    upload = Upload(
        clip_id=clip_id,
        signed_url=f"{settings.public_web_origin}/api/local-upload/{clip_id}",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    return SessionStartResponse(
        session_id=session_id,
        mode=mode,
        needs_help_steps=needs_help,
        skill_graph=sv.graph,
        skill_version_id=sv.id,
        master_name=master_name,
        trainee_name=user.display_name,
        live=Live(
            ephemeral_token=token, model=settings.model_live, expires_at=expires_at, config=live_cfg
        ),
        hazard_audio=hazards,
        upload=upload,
    )


@router.post("/sessions", response_model=SessionStartResponse)
async def start_session(
    body: SessionStartRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SessionStartResponse:
    sv = await get_skill_version(settings.database_url, body.skill_version_id)
    if sv is None:
        raise AppError(status_code=404, code="not_found", message="Skill version not found")
    require_role(user, sv.org_id, {"trainee", "owner", "supervisor", "master"})
    step_ids = [s.id for s in sv.graph.steps]
    url = resolve_database_url(settings.database_url)
    mastery = (
        await load_user_mastery_db(url, user.user_id, sv.id)
        if url
        else get_user_mastery(user.user_id, sv.id)
    )
    mode, needs_help = select_mode(mastery, step_ids, sv.graph.credential_policy.mastery_threshold)
    master_name = await _load_master_name(settings.database_url, sv)
    prompt = build_coach_system_instruction(
        graph=sv.graph,
        trainee_name=user.display_name,
        master_name=master_name,
        mode=mode,
        needs_help_steps=needs_help,
    )
    live_cfg = build_live_connect_config(
        system_instruction=prompt, voice_name=settings.tts_voice_name
    )
    token, expires_at = await mint_live_token(
        settings=settings,
        system_instruction=prompt,
        live_config_dict=live_cfg,
        allow_offline_stub=settings.app_env == "local",
    )
    return await _build_start_payload(
        sv, user, master_name, mode, needs_help, token, expires_at, live_cfg, settings
    )


@router.post("/sessions/{session_id}/calibration", response_model=OkResponse)
async def save_calibration(
    session_id: UUID,
    body: Calibration,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> OkResponse:
    ses = await _load_session(settings.database_url, session_id)
    if ses is None or ses.trainee_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    url = resolve_database_url(settings.database_url)
    if url:
        await save_calibration_db(url, session_id, body)
    else:
        ses.calibration = body
    return OkResponse(ok=True)


@router.post("/sessions/{session_id}/events", response_model=EventsAcceptedResponse)
async def append_events(
    session_id: UUID,
    body: EventsBatchRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> EventsAcceptedResponse:
    ses = await _load_session(settings.database_url, session_id)
    if ses is None or ses.trainee_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    for ev in body.events:
        if ev.type == Type.vlm_key:
            raise AppError(
                status_code=400,
                code="invalid_event",
                message="vlm_key events are written by /verify only",
            )
    url = resolve_database_url(settings.database_url)
    if url:
        await insert_step_events_db(url, session_id, body.events)
    else:
        ses.events.extend(body.events)
    bus = get_telemetry_bus()
    for ev in body.events:
        if ev.type in (Type.check_requested, Type.risk, Type.completed, Type.question):
            bus.record_trace(
                agent="coach",
                kind=Kind4.tool_call,
                summary=f"Coach event {ev.type.value} on {ev.step_id or 'session'}",
                scope=Scope4(session_id=session_id),
            )
    return EventsAcceptedResponse(accepted=len(body.events))


@router.post("/sessions/{session_id}/complete", response_model=SessionSummary)
async def complete_session(
    session_id: UUID,
    body: SessionCompleteRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SessionSummary:
    ses = await _load_session(settings.database_url, session_id)
    if ses is None or ses.trainee_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    if ses.summary is not None:
        return ses.summary
    url = resolve_database_url(settings.database_url)
    if url:
        existing_mastery = await load_user_mastery_db(url, user.user_id, ses.skill_version_id)
        prior_runs = await load_completed_runs_db(url, user.user_id, ses.skill_version_id)
        summary, updates = compute_session_summary(
            ses,
            body.status,
            existing_mastery,
            prior_runs,
            coach=body.coach,
            edge_fps=body.edge_fps,
        )
        await save_completion_db(
            url,
            session_id=session_id,
            user_id=user.user_id,
            skill_version_id=ses.skill_version_id,
            status=body.status,
            clip_id=body.clip_id,
            summary=summary,
            mastery_updates=updates,
        )
        return summary
    ses.status = body.status.value
    if body.clip_id:
        ses.clip_id = body.clip_id
    return finalize_mastery_and_summary(ses, body.status, coach=body.coach, edge_fps=body.edge_fps)


@router.get("/sessions/{session_id}", response_model=SessionDetailResponse)
async def get_session(
    session_id: UUID,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> SessionDetailResponse:
    ses = await _load_session(settings.database_url, session_id)
    if ses is None:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    if ses.trainee_user_id != user.user_id:
        require_role(user, ses.org_id, {"owner", "supervisor"})
    return SessionDetailResponse(
        session_id=ses.id,
        skill_version_id=ses.skill_version_id,
        mode=ses.mode.value,
        status=ses.status,
        summary=ses.summary,
        events=ses.events,
    )
