"""Effective consent scope resolution (BUILD_PLAN 21.3)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from uuid import UUID

from parampara.domain.generated import Action, ConsentRecord, Scope


def _matches_target(rec: ConsentRecord, clip_id: UUID | None, session_id: UUID | None) -> bool:
    if clip_id is not None and rec.target.clip_id == clip_id:
        return True
    return session_id is not None and rec.target.session_id == session_id


def effective_scopes(
    records: Sequence[ConsentRecord],
    *,
    clip_id: UUID | None = None,
    session_id: UUID | None = None,
    owner_user_id: UUID,
    at_time: datetime | None = None,
) -> set[Scope]:
    """Compute active scopes for a clip or session at at_time (owner-checked)."""
    now = (at_time or datetime.now(UTC)).astimezone(UTC)
    relevant = sorted(
        (
            r
            for r in records
            if _matches_target(r, clip_id, session_id)
            and r.created_at <= now
            and r.subject_user_id == owner_user_id
        ),
        key=lambda r: r.seq,
    )
    scope_expiry: dict[Scope, datetime | None] = {}
    for rec in relevant:
        if rec.action == Action.grant:
            exp = rec.expires_at.astimezone(UTC) if rec.expires_at is not None else None
            for scope in rec.scopes:
                scope_expiry[scope] = exp
        elif rec.action == Action.revoke:
            for scope in rec.scopes:
                scope_expiry.pop(scope, None)
    return {s for s, exp in scope_expiry.items() if exp is None or exp > now}


def has_effective_scope(
    records: Sequence[ConsentRecord],
    scope: Scope,
    *,
    clip_id: UUID | None = None,
    session_id: UUID | None = None,
    owner_user_id: UUID,
    at_time: datetime | None = None,
) -> bool:
    return scope in effective_scopes(
        records,
        clip_id=clip_id,
        session_id=session_id,
        owner_user_id=owner_user_id,
        at_time=at_time,
    )
