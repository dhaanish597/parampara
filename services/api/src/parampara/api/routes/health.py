"""Public health, DID document, and admin usage routes (BUILD_PLAN 12.2 & 20.1)."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from parampara.api.deps import CurrentUser, get_current_user
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import resolve_database_url
from parampara.db.repos.telemetry import fetch_usage_summary_db
from parampara.telemetry.recorder import get_telemetry_bus
from parampara.tools.multikey import build_did_document, keypair_from_seed_b64

router = APIRouter()


class HealthModels(BaseModel):
    live: str
    flash: str
    lite: str
    tts: str


class HealthResponse(BaseModel):
    ok: bool
    version: str
    models: HealthModels


class UsageItem(BaseModel):
    agent: str
    model: str
    calls: int
    input_tokens: int
    output_tokens: int
    cost_usd: float
    latencies_ms: list[int]


class AdminUsageResponse(BaseModel):
    items: list[UsageItem]


@router.get("/v1/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:  # noqa: B008
    return HealthResponse(
        ok=True,
        version=settings.app_version,
        models=HealthModels(
            live=settings.model_live,
            flash=settings.model_flash,
            lite=settings.model_lite,
            tts=settings.model_tts,
        ),
    )


@router.get("/.well-known/did.json")
async def did_document(settings: Settings = Depends(get_settings)) -> dict[str, Any]:  # noqa: B008
    _, pub_bytes = keypair_from_seed_b64(settings.issuer_ed25519_seed_b64)
    return build_did_document(
        issuer_did=settings.issuer_did,
        key_id=settings.issuer_key_id,
        public_key_bytes=pub_bytes,
    )


@router.get("/v1/admin/usage", response_model=AdminUsageResponse)
async def admin_usage(
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> AdminUsageResponse:
    has_admin = any(bool(roles & {"owner", "supervisor"}) for roles in user.memberships.values())
    if not has_admin:
        raise AppError(status_code=403, code="forbidden", message="Owner or supervisor required")
    url = resolve_database_url(settings.database_url)
    rows = await fetch_usage_summary_db(url) if url else get_telemetry_bus().usage_summary()
    return AdminUsageResponse(items=[UsageItem.model_validate(r) for r in rows])
