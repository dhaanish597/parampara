"""Licences and worker earnings routes (BUILD_PLAN 12.2, 23.1, T-042)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, Field

from parampara.api.deps import CurrentUser, get_current_user, require_role
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import open_db, resolve_database_url
from parampara.db.repos.idempotency import check_idempotency, hash_request_body, store_idempotency
from parampara.db.repos.licences_db import persist_licence_tx
from parampara.domain.generated import Licence, Payout, RoyaltyEvent, Scope3

router = APIRouter(prefix="/v1")


class CreateLicenceRequest(BaseModel):
    dataset_id: UUID
    buyer_org_id: UUID
    price_paise: int = Field(gt=0)
    scope: Scope3 = Scope3.robotics_commercial


class CreateLicenceResponse(BaseModel):
    licence: Licence
    royalty_events: list[RoyaltyEvent]
    payouts: list[Payout]


class LicenceDownloadResponse(BaseModel):
    licence_id: UUID
    dataset_id: UUID
    watermark_id: str
    export_path: str
    terms: dict[str, Any]


class EarningsResponse(BaseModel):
    user_id: UUID
    total_paise: int
    last_paid_at: datetime | None = None
    royalty_events: list[RoyaltyEvent]
    payouts: list[Payout]


@router.post("/licences", response_model=CreateLicenceResponse)
async def create_licence(
    body: CreateLicenceRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> CreateLicenceResponse:
    require_role(user, body.buyer_org_id, {"lab_buyer", "owner", "supervisor"})
    url = resolve_database_url(settings.database_url)
    if not url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    req_hash = hash_request_body(body.model_dump(mode="json"))
    if idempotency_key:
        cached = await check_idempotency(
            url,
            key=idempotency_key,
            route="/v1/licences",
            user_id=user.user_id,
            request_sha256=req_hash,
        )
        if cached is not None:
            return CreateLicenceResponse.model_validate(cached)
    lic, events, payouts = await persist_licence_tx(url, body, user.user_id, settings)
    res = CreateLicenceResponse(licence=lic, royalty_events=events, payouts=payouts)
    if idempotency_key:
        await store_idempotency(
            url,
            key=idempotency_key,
            route="/v1/licences",
            user_id=user.user_id,
            request_sha256=req_hash,
            response_body=res.model_dump(mode="json"),
        )
    return res


@router.get("/licences/{licence_id}/download", response_model=LicenceDownloadResponse)
async def download_licence(
    licence_id: UUID,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> LicenceDownloadResponse:
    url = resolve_database_url(settings.database_url)
    if not url:
        raise AppError(status_code=503, code="db_unavailable", message="Database is not configured")
    sql = (
        "SELECT l.id, l.dataset_id, l.buyer_org_id, l.watermark_id, l.terms, d.export_path "
        "FROM licences l JOIN datasets d ON d.id = l.dataset_id WHERE l.id = %s"
    )
    async with open_db(url) as conn:
        row = await (await conn.execute(sql, (licence_id,))).fetchone()
    if row is None:
        raise AppError(status_code=404, code="not_found", message="Licence not found")
    require_role(user, UUID(str(row["buyer_org_id"])), {"lab_buyer", "owner", "supervisor"})
    return LicenceDownloadResponse(
        licence_id=UUID(str(row["id"])),
        dataset_id=UUID(str(row["dataset_id"])),
        watermark_id=str(row["watermark_id"]),
        export_path=str(row["export_path"]),
        terms=dict(row["terms"]),
    )


@router.get("/earnings/me", response_model=EarningsResponse)
async def my_earnings(
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> EarningsResponse:
    url = resolve_database_url(settings.database_url)
    if not url:
        return EarningsResponse(user_id=user.user_id, total_paise=0, royalty_events=[], payouts=[])
    re_sql = (
        "SELECT id, licence_id, role::text AS role, beneficiary_user_id, beneficiary_org_id, "
        "amount_paise, basis, created_at FROM royalty_events "
        "WHERE beneficiary_user_id = %s ORDER BY created_at DESC"
    )
    p_sql = (
        "SELECT p.id, p.royalty_event_id, p.provider::text AS provider, p.provider_ref, "
        "p.status, p.created_at FROM payouts p "
        "JOIN royalty_events re ON re.id = p.royalty_event_id "
        "WHERE re.beneficiary_user_id = %s ORDER BY p.created_at DESC"
    )
    async with open_db(url) as conn:
        re_rows = await (await conn.execute(re_sql, (user.user_id,))).fetchall()
        p_rows = await (await conn.execute(p_sql, (user.user_id,))).fetchall()
    events = [RoyaltyEvent.model_validate(dict(r)) for r in re_rows]
    payouts = [Payout.model_validate(dict(r)) for r in p_rows]
    total = sum(e.amount_paise for e in events)
    last_paid = max((p.created_at for p in payouts if p.status.value == "processed"), default=None)
    return EarningsResponse(
        user_id=user.user_id,
        total_paise=total,
        last_paid_at=last_paid,
        royalty_events=events,
        payouts=payouts,
    )
