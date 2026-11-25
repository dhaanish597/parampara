"""CR-004: Fresh single-use Live token endpoint for session reconnect (6/min)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from parampara.agents.coach.builder import build_coach_system_instruction, build_live_connect_config
from parampara.agents.coach.token import mint_live_token
from parampara.api.deps import CurrentUser, get_current_user
from parampara.api.errors import AppError
from parampara.api.routes.sessions import _load_master_name, _load_session
from parampara.api.settings import Settings, get_settings
from parampara.db.repos.skill_versions import get_skill_version
from parampara.domain.generated import Live

router = APIRouter(prefix="/v1")
_HITS: dict[UUID, list[float]] = {}


class LiveTokenRequest(BaseModel):
    resumption_handle: str | None = None


def _enforce_rate_limit(session_id: UUID) -> None:
    now = datetime.now(UTC).timestamp()
    recent = [t for t in _HITS.get(session_id, []) if now - t < 60.0]
    if len(recent) >= 6:
        raise AppError(status_code=429, code="rate_limited", message="Max 6 live-token/min")
    recent.append(now)
    _HITS[session_id] = recent


@router.post("/sessions/{session_id}/live-token", response_model=Live)
async def refresh_live_token(
    session_id: UUID,
    body: LiveTokenRequest,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> Live:
    """Mint a fresh single-use Live token carrying resumption_handle for the session trainee."""
    ses = await _load_session(settings.database_url, session_id)
    if ses is None or ses.trainee_user_id != user.user_id:
        raise AppError(status_code=404, code="not_found", message="Session not found")
    _enforce_rate_limit(session_id)
    sv = await get_skill_version(settings.database_url, ses.skill_version_id)
    master_name = await _load_master_name(settings.database_url, sv) if sv else "Master"
    prompt = build_coach_system_instruction(
        graph=ses.graph,
        trainee_name=user.display_name,
        master_name=master_name,
        mode=ses.mode,
        needs_help_steps=[],
    )
    live_cfg = build_live_connect_config(
        system_instruction=prompt,
        voice_name=settings.tts_voice_name,
        resumption_handle=body.resumption_handle,
    )
    token, expires_at = await mint_live_token(
        settings=settings,
        system_instruction=prompt,
        live_config_dict=live_cfg,
        allow_offline_stub=settings.app_env == "local",
    )
    return Live(
        ephemeral_token=token, model=settings.model_live, expires_at=expires_at, config=live_cfg
    )
