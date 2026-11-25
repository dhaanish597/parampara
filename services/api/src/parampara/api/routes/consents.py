"""Consent ledger API endpoints (BUILD_PLAN 12.2 & 21)."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel

from parampara.api.deps import CurrentUser, get_current_user
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import open_db, resolve_database_url
from parampara.db.repos.consents import (
    append_consent_db,
    list_all_consents_db,
    list_user_consents_db,
)
from parampara.db.repos.idempotency import check_idempotency, hash_request_body, store_idempotency
from parampara.domain.generated import Action, ConsentRecord, ConsentRequest
from parampara.tools.ledger import get_consent_ledger, verify_chain
from parampara.tools.scopes import effective_scopes

router = APIRouter(prefix="/v1")
VALID_NOTICE_VERSIONS = frozenset({"consent-notice-v1"})


class MyConsentsResponse(BaseModel):
    records: list[ConsentRecord]
    effective_by_clip: dict[str, list[str]]


class VerifyChainResponse(BaseModel):
    ok: bool
    length: int
    head_hash: str
    first_bad_seq: int | None = None


async def _resolve_target_owner(
    *, clip_id: UUID | None, session_id: UUID | None, database_url: str
) -> UUID | None:
    url = resolve_database_url(database_url)
    if not url:
        return None
    async with open_db(url) as conn:
        if clip_id is not None:
            row = await (
                await conn.execute("SELECT owner_user_id FROM clips WHERE id = %s", (clip_id,))
            ).fetchone()
            return UUID(str(row["owner_user_id"])) if row else None
        row = await (
            await conn.execute("SELECT trainee_user_id FROM sessions WHERE id = %s", (session_id,))
        ).fetchone()
        return UUID(str(row["trainee_user_id"])) if row else None


def _validate_consent_request(body: ConsentRequest) -> None:
    if body.notice_version not in VALID_NOTICE_VERSIONS:
        raise AppError(
            status_code=400, code="unknown_notice_version", message="Unknown consent notice version"
        )
    if not body.scopes:
        raise AppError(
            status_code=400, code="scopes_required", message="At least one scope required"
        )
    if body.action == Action.grant and not body.comprehension_passed:
        raise AppError(
            status_code=400,
            code="comprehension_required",
            message="Comprehension question must be passed before granting consent",
        )
    if (body.target.clip_id is None) == (body.target.session_id is None):
        raise AppError(
            status_code=400,
            code="invalid_target",
            message="Specify exactly one of clip_id or session_id",
        )
    if body.expires_at is not None and body.expires_at.astimezone(UTC) <= datetime.now(UTC):
        raise AppError(
            status_code=400, code="invalid_expiry", message="expires_at must be in the future"
        )


async def _append_consent(url: str, user_id: UUID, body: ConsentRequest) -> ConsentRecord:
    if url:
        return await append_consent_db(
            url,
            subject_user_id=user_id,
            action=body.action,
            clip_id=body.target.clip_id,
            session_id=body.target.session_id,
            scopes=body.scopes,
            expires_at=body.expires_at,
            notice_version=body.notice_version,
            comprehension_passed=body.comprehension_passed,
        )
    return await get_consent_ledger().append(
        subject_user_id=user_id,
        action=body.action,
        clip_id=body.target.clip_id,
        session_id=body.target.session_id,
        scopes=body.scopes,
        expires_at=body.expires_at,
        notice_version=body.notice_version,
        comprehension_passed=body.comprehension_passed,
    )


async def _check_owner_and_revoke(url: str, user_id: UUID, body: ConsentRequest) -> None:
    owner_id = await _resolve_target_owner(
        clip_id=body.target.clip_id,
        session_id=body.target.session_id,
        database_url=url,
    )
    if owner_id is None:
        raise AppError(status_code=404, code="target_not_found", message="Target not found")
    if owner_id != user_id:
        raise AppError(
            status_code=403, code="forbidden", message="Only the owner can manage consent"
        )
    if body.action != Action.revoke:
        return
    existing = (
        await list_user_consents_db(url, owner_id) if url else get_consent_ledger().all_records()
    )
    active = effective_scopes(
        existing,
        clip_id=body.target.clip_id,
        session_id=body.target.session_id,
        owner_user_id=owner_id,
    )
    if not (active & set(body.scopes)):
        raise AppError(
            status_code=400, code="nothing_to_revoke", message="No active scope to revoke"
        )


@router.post("/consents", response_model=ConsentRecord)
async def create_consent(
    body: ConsentRequest,
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> ConsentRecord:
    _validate_consent_request(body)
    url = resolve_database_url(settings.database_url)
    req_hash = hash_request_body(body.model_dump(mode="json"))
    if idempotency_key and url:
        cached = await check_idempotency(
            url,
            key=idempotency_key,
            route="/v1/consents",
            user_id=user.user_id,
            request_sha256=req_hash,
        )
        if cached is not None:
            return ConsentRecord.model_validate(cached)
    await _check_owner_and_revoke(url, user.user_id, body)
    rec = await _append_consent(url, user.user_id, body)
    if idempotency_key and url:
        await store_idempotency(
            url,
            key=idempotency_key,
            route="/v1/consents",
            user_id=user.user_id,
            request_sha256=req_hash,
            response_body=rec.model_dump(mode="json"),
        )
    return rec


@router.get("/consents/me", response_model=MyConsentsResponse)
async def my_consents(
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> MyConsentsResponse:
    url = resolve_database_url(settings.database_url)
    records = (
        await list_user_consents_db(url, user.user_id)
        if url
        else get_consent_ledger().for_user(user.user_id)
    )
    clip_ids: set[UUID] = {r.target.clip_id for r in records if r.target.clip_id is not None}
    effective = {
        str(cid): sorted(
            s.value for s in effective_scopes(records, clip_id=cid, owner_user_id=user.user_id)
        )
        for cid in clip_ids
    }
    return MyConsentsResponse(records=records, effective_by_clip=effective)


@router.get("/consents/verify-chain", response_model=VerifyChainResponse)
async def verify_consent_chain(
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> VerifyChainResponse:
    url = resolve_database_url(settings.database_url)
    records = await list_all_consents_db(url) if url else get_consent_ledger().all_records()
    check = verify_chain(records)
    return VerifyChainResponse(
        ok=check.ok,
        length=check.length,
        head_hash=check.head_hash,
        first_bad_seq=check.first_bad_seq,
    )
