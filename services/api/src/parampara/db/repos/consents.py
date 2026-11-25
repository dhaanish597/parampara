"""Transactional PostgreSQL consent ledger repository (BUILD_PLAN 21.2, T-034)."""

from __future__ import annotations

from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.db.pool import open_db
from parampara.domain.generated import Action, ConsentRecord, Scope, Target
from parampara.tools.ledger import GENESIS_HASH, compute_consent_hash, purpose_for_scopes


def _row_to_consent(row: dict[str, Any]) -> ConsentRecord:
    return ConsentRecord(
        id=UUID(str(row["id"])),
        seq=int(row["seq"]),
        subject_user_id=UUID(str(row["subject_user_id"])),
        action=Action(str(row["action"])),
        target=Target(
            clip_id=UUID(str(row["clip_id"])) if row["clip_id"] else None,
            session_id=UUID(str(row["session_id"])) if row["session_id"] else None,
        ),
        scopes=[Scope(s) for s in row["scopes"]],
        purpose=str(row["purpose"]),
        expires_at=row["expires_at"],
        notice_version=str(row["notice_version"]),
        comprehension_passed=bool(row["comprehension_passed"]),
        prev_hash=str(row["prev_hash"]),
        hash=str(row["hash"]),
        created_at=row["created_at"],
    )


def _build_record(
    *,
    seq: int,
    prev_hash: str,
    subject_user_id: UUID,
    action: Action,
    clip_id: UUID | None,
    session_id: UUID | None,
    scopes: list[Scope],
    expires_at: datetime | None,
    notice_version: str,
    comprehension_passed: bool,
    ts: datetime,
) -> ConsentRecord:
    draft = ConsentRecord(
        id=uuid4(),
        seq=seq,
        subject_user_id=subject_user_id,
        action=action,
        target=Target(clip_id=clip_id, session_id=session_id),
        scopes=scopes,
        purpose=purpose_for_scopes(scopes),
        expires_at=expires_at,
        notice_version=notice_version,
        comprehension_passed=comprehension_passed,
        created_at=ts,
        prev_hash=prev_hash,
        hash=GENESIS_HASH,
    )
    return draft.model_copy(update={"hash": compute_consent_hash(draft)})


async def _insert_record_row(conn: Any, final: ConsentRecord) -> None:
    sql = (
        "INSERT INTO consent_records "
        "(id, seq, subject_user_id, action, clip_id, session_id, scopes, purpose, "
        "expires_at, notice_version, comprehension_passed, prev_hash, hash, created_at) "
        "VALUES (%s, %s, %s, %s::consent_action, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    await conn.execute(
        sql,
        (
            final.id,
            final.seq,
            final.subject_user_id,
            final.action.value,
            final.target.clip_id,
            final.target.session_id,
            [s.value for s in final.scopes],
            final.purpose,
            final.expires_at,
            final.notice_version,
            final.comprehension_passed,
            final.prev_hash,
            final.hash,
            final.created_at,
        ),
    )


async def append_consent_db(
    database_url: str,
    *,
    subject_user_id: UUID,
    action: Action,
    clip_id: UUID | None,
    session_id: UUID | None,
    scopes: Sequence[Scope],
    expires_at: datetime | None,
    notice_version: str,
    comprehension_passed: bool,
    created_at: datetime | None = None,
) -> ConsentRecord:
    """Append a hash-chained consent row under SELECT ... FOR UPDATE on consent_chain_head."""
    sorted_scopes = sorted(set(scopes), key=lambda s: s.value)
    ts = (created_at or datetime.now(UTC)).replace(microsecond=0)
    head_sql = "SELECT last_seq, last_hash FROM consent_chain_head WHERE id = 1 FOR UPDATE"
    upd_sql = "UPDATE consent_chain_head SET last_seq = %s, last_hash = %s WHERE id = 1"
    async with open_db(database_url) as conn, conn.transaction():
        head = await (await conn.execute(head_sql)).fetchone()
        if head is None:
            raise RuntimeError("consent_chain_head row id=1 is missing")
        final = _build_record(
            seq=int(head["last_seq"]) + 1,
            prev_hash=str(head["last_hash"]),
            subject_user_id=subject_user_id,
            action=action,
            clip_id=clip_id,
            session_id=session_id,
            scopes=sorted_scopes,
            expires_at=expires_at,
            notice_version=notice_version,
            comprehension_passed=comprehension_passed,
            ts=ts,
        )
        await _insert_record_row(conn, final)
        await conn.execute(upd_sql, (final.seq, final.hash))
    return final


async def list_all_consents_db(database_url: str) -> list[ConsentRecord]:
    sql = (
        "SELECT id, seq, subject_user_id, action::text AS action, clip_id, session_id, "
        "scopes, purpose, expires_at, notice_version, comprehension_passed, "
        "prev_hash, hash, created_at FROM consent_records ORDER BY seq ASC"
    )
    async with open_db(database_url) as conn:
        rows = await (await conn.execute(sql)).fetchall()
    return [_row_to_consent(dict(r)) for r in rows]


async def list_user_consents_db(database_url: str, user_id: UUID) -> list[ConsentRecord]:
    sql = (
        "SELECT id, seq, subject_user_id, action::text AS action, clip_id, session_id, "
        "scopes, purpose, expires_at, notice_version, comprehension_passed, "
        "prev_hash, hash, created_at FROM consent_records "
        "WHERE subject_user_id = %s ORDER BY seq ASC"
    )
    async with open_db(database_url) as conn:
        rows = await (await conn.execute(sql, (user_id,))).fetchall()
    return [_row_to_consent(dict(r)) for r in rows]
