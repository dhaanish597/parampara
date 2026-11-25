"""Tests for consent hash-chain ledger, ownership (P0-7), scopes, and API (T-034)."""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import httpx
import pytest

from parampara.api.deps import CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.routes import consents as consents_route
from parampara.domain.generated import Action, Scope
from parampara.tools.ledger import InMemoryConsentLedger, verify_chain
from parampara.tools.scopes import effective_scopes


async def test_concurrent_writers_keep_chain_valid() -> None:
    ledger = InMemoryConsentLedger()
    uid, clip_a, clip_b = uuid4(), uuid4(), uuid4()

    async def writer(clip_id: UUID, count: int) -> None:
        for _ in range(count):
            await ledger.append(
                subject_user_id=uid,
                action=Action.grant,
                clip_id=clip_id,
                session_id=None,
                scopes=[Scope.train_own_org],
                expires_at=None,
                notice_version="consent-notice-v1",
                comprehension_passed=True,
            )

    await asyncio.gather(writer(clip_a, 10), writer(clip_b, 10))
    check = verify_chain(ledger.all_records())
    assert check.ok is True and check.length == 20 and check.first_bad_seq is None


async def test_verify_chain_detects_tampered_record() -> None:
    ledger = InMemoryConsentLedger()
    uid, clip = uuid4(), uuid4()
    for _ in range(3):
        await ledger.append(
            subject_user_id=uid,
            action=Action.grant,
            clip_id=clip,
            session_id=None,
            scopes=[Scope.train_own_org],
            expires_at=None,
            notice_version="consent-notice-v1",
            comprehension_passed=True,
        )
    recs = ledger.all_records()
    recs[1] = recs[1].model_copy(update={"purpose": "tampered"})
    check = verify_chain(recs)
    assert check.ok is False and check.first_bad_seq == 2


async def _grant(
    ledger: InMemoryConsentLedger,
    uid: UUID,
    clip: UUID,
    scopes: list[Scope],
    created_at: datetime,
    expires_at: datetime | None = None,
) -> None:
    await ledger.append(
        subject_user_id=uid,
        action=Action.grant,
        clip_id=clip,
        session_id=None,
        scopes=scopes,
        expires_at=expires_at,
        notice_version="consent-notice-v1",
        comprehension_passed=True,
        created_at=created_at,
    )


async def test_effective_scopes_owner_check_revoke_and_shorter_regrant() -> None:
    ledger = InMemoryConsentLedger()
    owner, intruder, clip = uuid4(), uuid4(), uuid4()
    t0 = datetime(2026, 11, 26, 10, 0, tzinfo=UTC)
    await _grant(ledger, intruder, clip, [Scope.robotics_commercial], t0)
    await _grant(
        ledger,
        owner,
        clip,
        [Scope.train_own_org],
        t0 + timedelta(minutes=1),
        t0 + timedelta(hours=5),
    )
    await _grant(
        ledger,
        owner,
        clip,
        [Scope.train_own_org],
        t0 + timedelta(minutes=2),
        t0 + timedelta(hours=1),
    )
    recs = ledger.all_records()
    assert effective_scopes(
        recs, clip_id=clip, owner_user_id=owner, at_time=t0 + timedelta(minutes=10)
    ) == {Scope.train_own_org}
    assert (
        effective_scopes(recs, clip_id=clip, owner_user_id=owner, at_time=t0 + timedelta(hours=2))
        == set()
    )


async def test_consent_api_enforces_owner_and_validations(monkeypatch: object) -> None:
    owner_id, other_id, clip_id = uuid4(), uuid4(), uuid4()

    async def _fake_owner(
        *, clip_id: UUID | None, session_id: UUID | None, database_url: str
    ) -> UUID | None:
        return owner_id if clip_id is not None else None

    monkeypatch.setattr(consents_route, "_resolve_target_owner", _fake_owner)  # type: ignore[attr-defined]
    app = create_app()
    current = {"u": CurrentUser(user_id=other_id, display_name="B", pseudonym="b")}
    app.dependency_overrides[get_current_user] = lambda: current["u"]
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        body = {
            "action": "grant",
            "target": {"clip_id": str(clip_id)},
            "scopes": ["robotics_commercial"],
            "expires_at": None,
            "notice_version": "consent-notice-v1",
            "comprehension_passed": True,
        }
        # P0-7: User B cannot grant consent on User A's clip
        assert (await client.post("/v1/consents", json=body)).status_code == 403
        # Owner succeeds
        current["u"] = CurrentUser(user_id=owner_id, display_name="A", pseudonym="a")
        ok = await client.post("/v1/consents", json=body)
        assert ok.status_code == 200 and len(ok.json()["hash"]) == 64
        # P1: Unknown notice version rejected
        bad_notice = dict(body, notice_version="unknown-v9")
        assert (await client.post("/v1/consents", json=bad_notice)).status_code == 400
        vc = await client.get("/v1/consents/verify-chain")
        assert vc.status_code == 200 and vc.json()["ok"] is True


def test_effective_scopes_requires_the_target_owner() -> None:
    with pytest.raises(TypeError):
        effective_scopes([], clip_id=uuid4())  # type: ignore[call-arg]
