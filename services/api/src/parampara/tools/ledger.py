"""Append-only SHA-256 hash-chained consent ledger (BUILD_PLAN 21.2)."""

from __future__ import annotations

import asyncio
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.domain.generated import Action, ConsentRecord, Scope, Target
from parampara.tools.hashing import sha256_canonical_json

GENESIS_HASH = "0" * 64

SCOPE_PURPOSE_MAP: dict[Scope, str] = {
    Scope.train_own_org: "Internal factory coaching and aggregate dashboards",
    Scope.train_other_employers: "Cross-employer vocational coaching for this skill",
    Scope.robotics_research: "Non-commercial robotics research datasets (no surveillance)",
    Scope.robotics_commercial: (
        "Commercial robotics datasets with worker royalties (no surveillance)"
    ),
}


@dataclass(frozen=True)
class ChainCheck:
    ok: bool
    length: int
    head_hash: str
    first_bad_seq: int | None


def _iso_z(dt: datetime | None) -> str | None:
    if dt is None:
        return None
    return dt.astimezone(UTC).isoformat().replace("+00:00", "Z")


def canonical_consent_payload(record: ConsentRecord) -> dict[str, Any]:
    """Exact 12-key canonical dict specified in BUILD_PLAN 21.2."""
    return {
        "seq": record.seq,
        "subject_user_id": str(record.subject_user_id),
        "action": record.action.value,
        "clip_id": str(record.target.clip_id) if record.target.clip_id else None,
        "session_id": str(record.target.session_id) if record.target.session_id else None,
        "scopes": sorted(s.value for s in record.scopes),
        "purpose": record.purpose,
        "expires_at": _iso_z(record.expires_at),
        "notice_version": record.notice_version,
        "comprehension_passed": record.comprehension_passed,
        "created_at": _iso_z(record.created_at),
        "prev_hash": record.prev_hash,
    }


def compute_consent_hash(record: ConsentRecord) -> str:
    return sha256_canonical_json(canonical_consent_payload(record))


def verify_chain(records: Sequence[ConsentRecord]) -> ChainCheck:
    """Walk records by seq, verify prev_hash linkage and recomputed hash (BUILD_PLAN 21.2)."""
    ordered = sorted(records, key=lambda r: r.seq)
    prev = GENESIS_HASH
    for idx, rec in enumerate(ordered, start=1):
        if rec.seq != idx or rec.prev_hash != prev:
            return ChainCheck(ok=False, length=len(ordered), head_hash=prev, first_bad_seq=rec.seq)
        if compute_consent_hash(rec) != rec.hash:
            return ChainCheck(ok=False, length=len(ordered), head_hash=prev, first_bad_seq=rec.seq)
        prev = rec.hash
    return ChainCheck(ok=True, length=len(ordered), head_hash=prev, first_bad_seq=None)


def purpose_for_scopes(scopes: Sequence[Scope]) -> str:
    if not scopes:
        return "Revocation of prior consent"
    return "; ".join(SCOPE_PURPOSE_MAP[s] for s in sorted(set(scopes), key=lambda x: x.value))


class InMemoryConsentLedger:
    """Async-locked append-only ledger mirroring the Postgres FOR UPDATE head lock."""

    def __init__(self) -> None:
        self._lock = asyncio.Lock()
        self._records: list[ConsentRecord] = []

    async def append(
        self,
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
        async with self._lock:
            seq = len(self._records) + 1
            prev_hash = self._records[-1].hash if self._records else GENESIS_HASH
            sorted_scopes = sorted(set(scopes), key=lambda s: s.value)
            ts = (created_at or datetime.now(UTC)).replace(microsecond=0)
            draft = ConsentRecord(
                id=uuid4(),
                seq=seq,
                subject_user_id=subject_user_id,
                action=action,
                target=Target(clip_id=clip_id, session_id=session_id),
                scopes=sorted_scopes,
                purpose=purpose_for_scopes(sorted_scopes),
                expires_at=expires_at,
                notice_version=notice_version,
                comprehension_passed=comprehension_passed,
                created_at=ts,
                prev_hash=prev_hash,
                hash=GENESIS_HASH,
            )
            final = draft.model_copy(update={"hash": compute_consent_hash(draft)})
            self._records.append(final)
            return final

    def all_records(self) -> list[ConsentRecord]:
        return list(self._records)

    def for_user(self, user_id: UUID) -> list[ConsentRecord]:
        return [r for r in self._records if r.subject_user_id == user_id]


_DEFAULT_LEDGER = InMemoryConsentLedger()


def get_consent_ledger() -> InMemoryConsentLedger:
    return _DEFAULT_LEDGER
