"""Real PostgreSQL persistence tests against local Supabase (Phase 2a)."""

from __future__ import annotations

import asyncio
import os
from uuid import UUID, uuid4

import httpx
import psycopg
import pytest

from parampara.api.deps import ALL_DEMO_ROLES, CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.settings import DEFAULT_DEMO_ORG_ID, Settings, get_settings
from parampara.db.pool import close_pool, init_pool, pool_is_open
from parampara.db.repos.consents import append_consent_db, list_all_consents_db
from parampara.db.repos.skill_versions import DEMO_SKILL_VERSION_ID
from parampara.db.repos.telemetry import fetch_recent_traces_db
from parampara.domain.generated import Action, Kind4, Scope, Scope4
from parampara.telemetry.recorder import TelemetryBus
from parampara.tools.ledger import verify_chain

SUPABASE_DB_URL = os.environ.get(
    "DATABASE_URL", "postgresql://postgres:postgres@127.0.0.1:54322/postgres"
)
POOJA_ID = UUID("20000000-0000-4000-8000-000000000003")


def _supabase_reachable() -> bool:
    try:
        with psycopg.connect(SUPABASE_DB_URL, connect_timeout=1) as conn:
            conn.execute("SELECT 1")
        return True
    except psycopg.Error:
        return False


def _db_app(user: CurrentUser) -> object:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        database_url=SUPABASE_DB_URL, gemini_api_key="", app_env="local"
    )
    app.dependency_overrides[get_current_user] = lambda: user
    return app


async def test_pool_opens_and_closes_and_telemetry_mirrors_to_postgres() -> None:
    if not _supabase_reachable():
        pytest.skip("Local Supabase Postgres (54322) not reachable")
    await init_pool(SUPABASE_DB_URL)
    assert pool_is_open() is True
    try:
        sid = uuid4()
        bus = TelemetryBus()
        bus.configure(database_url=SUPABASE_DB_URL)
        bus.record_trace(
            agent="verifier", kind=Kind4.verdict, summary="pool-test", scope=Scope4(session_id=sid)
        )
        await bus.flush()
        rows = await fetch_recent_traces_db(SUPABASE_DB_URL, session_id=sid)
        assert any(r.summary == "pool-test" for r in rows)
    finally:
        await close_pool()
        assert pool_is_open() is False


async def test_consent_db_for_update_two_connection_concurrency() -> None:
    if not _supabase_reachable():
        pytest.skip("Local Supabase Postgres (54322) not reachable")
    clip_a, clip_b = uuid4(), uuid4()
    with psycopg.connect(SUPABASE_DB_URL, autocommit=True) as conn:
        for cid in (clip_a, clip_b):
            conn.execute(
                "INSERT INTO clips (id, org_id, owner_user_id, kind, storage_path, mime) "
                "VALUES (%s, %s, %s, 'session', %s, 'video/webm') ON CONFLICT DO NOTHING",
                (cid, DEFAULT_DEMO_ORG_ID, POOJA_ID, f"clips/{cid}.webm"),
            )

    async def writer(cid: UUID) -> None:
        for _ in range(5):
            await append_consent_db(
                SUPABASE_DB_URL,
                subject_user_id=POOJA_ID,
                action=Action.grant,
                clip_id=cid,
                session_id=None,
                scopes=[Scope.train_own_org],
                expires_at=None,
                notice_version="consent-notice-v1",
                comprehension_passed=True,
            )

    await asyncio.gather(writer(clip_a), writer(clip_b))
    check = verify_chain(await list_all_consents_db(SUPABASE_DB_URL))
    assert check.ok is True and check.length >= 10 and check.first_bad_seq is None


async def test_session_persists_and_consent_on_api_session_succeeds() -> None:
    if not _supabase_reachable():
        pytest.skip("Local Supabase Postgres (54322) not reachable")
    user = CurrentUser(
        user_id=POOJA_ID,
        display_name="Pooja (demo)",
        pseudonym="pooja_trainee",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    req_start = {
        "skill_version_id": str(DEMO_SKILL_VERSION_ID),
        "device": {"ua": "t", "w": 390, "h": 844},
    }
    app1: object = _db_app(user)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app1),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        start = await c.post("/v1/sessions", json=req_start)
        assert start.status_code == 200
        sid = start.json()["session_id"]
        consent_body = {
            "action": "grant",
            "target": {"session_id": sid},
            "scopes": ["train_own_org"],
            "expires_at": None,
            "notice_version": "consent-notice-v1",
            "comprehension_passed": True,
        }
        consent = await c.post("/v1/consents", json=consent_body)
        assert consent.status_code == 200 and len(consent.json()["hash"]) == 64
        bad = await c.post("/v1/sessions", json={})
        assert bad.status_code == 422 and bad.json()["error"]["code"] == "validation_error"
    app2: object = _db_app(user)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app2),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c2:
        got = await c2.get(f"/v1/sessions/{sid}")
        assert got.status_code == 200 and got.json()["session_id"] == sid


def _seed_test_dataset() -> UUID:
    ds_id = uuid4()
    with psycopg.connect(SUPABASE_DB_URL, autocommit=True) as conn:
        conn.execute(
            "INSERT INTO datasets (id, skill_version_id, scope, name, episode_count, "
            "hours, export_path, data_card_md) "
            "VALUES (%s, %s, 'robotics_commercial', 'phase2-test-ds', 2, 0.2, "
            "'datasets/test', '# test')",
            (ds_id, DEMO_SKILL_VERSION_ID),
        )
    return ds_id


async def test_idempotency_licences_and_earnings_on_real_db() -> None:
    if not _supabase_reachable():
        pytest.skip("Local Supabase Postgres (54322) not reachable")
    user = CurrentUser(
        user_id=POOJA_ID,
        display_name="Pooja (demo)",
        pseudonym="pooja_trainee",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    ds_id, idem = _seed_test_dataset(), f"lic-{uuid4().hex[:12]}"
    payload = {
        "dataset_id": str(ds_id),
        "buyer_org_id": DEFAULT_DEMO_ORG_ID,
        "price_paise": 100000,
        "scope": "robotics_commercial",
    }
    app: object = _db_app(user)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app),  # type: ignore[arg-type]
        base_url="http://test",
    ) as c:
        r1 = await c.post("/v1/licences", json=payload, headers={"Idempotency-Key": idem})
        assert r1.status_code == 200 and r1.json()["licence"]["price_paise"] == 100000
        assert sum(e["amount_paise"] for e in r1.json()["royalty_events"]) == 100000
        r2 = await c.post("/v1/licences", json=payload, headers={"Idempotency-Key": idem})
        assert r2.status_code == 200 and r2.json()["licence"]["id"] == r1.json()["licence"]["id"]
        r3 = await c.post(
            "/v1/licences",
            json={**payload, "price_paise": 200000},
            headers={"Idempotency-Key": idem},
        )
        assert r3.status_code == 409 and r3.json()["error"]["code"] == "idempotency_conflict"
        dl = await c.get(f"/v1/licences/{r1.json()['licence']['id']}/download")
        assert dl.status_code == 200 and dl.json()["export_path"] == "datasets/test"
        earn = await c.get("/v1/earnings/me")
        assert earn.status_code == 200 and "total_paise" in earn.json()
