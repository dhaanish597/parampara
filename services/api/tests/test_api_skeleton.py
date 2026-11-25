"""API skeleton tests: health, DID doc, JWT auth (P0-1), demo join, skill-versions, SSE (T-011)."""

from __future__ import annotations

import asyncio
import base64
import json
import os
from uuid import UUID, uuid4

import httpx
import jwt
import psycopg

from parampara.api.deps import ALL_DEMO_ROLES, CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.settings import DEFAULT_DEMO_ORG_ID, Settings, get_settings
from parampara.db.repos.skill_versions import DEMO_SKILL_VERSION_ID
from parampara.domain.generated import Kind4, Scope4
from parampara.telemetry.recorder import get_telemetry_bus

TEST_JWT_SECRET = "parampara-unit-test-jwt-secret-32b!"  # noqa: S105


def _sign_jwt(
    sub: UUID, *, is_anonymous: bool = False, extra: dict[str, object] | None = None
) -> str:
    payload: dict[str, object] = {
        "sub": str(sub),
        "aud": "authenticated",
        "is_anonymous": is_anonymous,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, TEST_JWT_SECRET, algorithm="HS256")


def _local_db_url() -> str:
    candidates = [
        os.environ.get("DATABASE_URL"),
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        f"postgresql://{os.environ.get('USER', 'dhaanish')}@127.0.0.1:5432/parampara_dev",
    ]
    for url in candidates:
        if not url:
            continue
        try:
            with psycopg.connect(url, connect_timeout=1) as conn:
                conn.execute("SELECT 1")
            return url
        except psycopg.Error:
            continue
    return ""


async def test_health_and_did_document() -> None:
    app = create_app()
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        r = await client.get("/v1/health")
        assert r.status_code == 200 and r.json()["ok"] is True
        assert "X-Request-Id" in r.headers
        did = await client.get("/.well-known/did.json")
        assert did.status_code == 200
        assert did.json()["verificationMethod"][0]["publicKeyMultibase"].startswith("z6Mk")


async def test_p0_1_rejects_forged_unsigned_and_demo_tokens() -> None:
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_jwt_secret=TEST_JWT_SECRET, database_url=""
    )

    def b64(obj: dict[str, object]) -> str:
        return base64.urlsafe_b64encode(json.dumps(obj).encode()).rstrip(b"=").decode()

    forged = (
        f"{b64({'alg': 'none', 'typ': 'JWT'})}.{b64({'sub': str(uuid4()), 'roles': ['owner']})}.sig"
    )
    wrong_sig = jwt.encode(
        {"sub": str(uuid4())}, "wrong-secret-32-bytes-minimum-key!", algorithm="HS256"
    )
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        assert (await client.get("/v1/me")).status_code == 401
        assert (
            await client.get("/v1/me", headers={"Authorization": f"Bearer {forged}"})
        ).status_code == 401
        assert (
            await client.get("/v1/me", headers={"Authorization": f"Bearer {wrong_sig}"})
        ).status_code == 401
        assert (
            await client.get("/v1/me", headers={"Authorization": "Bearer demo:judge1"})
        ).status_code == 401
        wrong_aud = jwt.encode(
            {"sub": str(uuid4()), "aud": "service"}, TEST_JWT_SECRET, algorithm="HS256"
        )
        assert (
            await client.get("/v1/me", headers={"Authorization": f"Bearer {wrong_aud}"})
        ).status_code == 401


async def test_p0_1_ignores_jwt_roles_and_persists_anon_demo_join_in_db() -> None:
    db_url = _local_db_url()
    app = create_app()
    app.dependency_overrides[get_settings] = lambda: Settings(
        supabase_jwt_secret=TEST_JWT_SECRET, database_url=db_url
    )
    uid = uuid4()
    tok_non_anon = _sign_jwt(uid, is_anonymous=False, extra={"roles": ["owner", "supervisor"]})
    tok_anon = _sign_jwt(uid, is_anonymous=True)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        me = await client.get("/v1/me", headers={"Authorization": f"Bearer {tok_non_anon}"})
        assert me.status_code == 200 and me.json()["memberships"] == []
        assert (
            await client.post("/v1/demo/join", headers={"Authorization": f"Bearer {tok_non_anon}"})
        ).status_code == 403
        if db_url:
            joined = await client.post(
                "/v1/demo/join", headers={"Authorization": f"Bearer {tok_anon}"}
            )
            assert joined.status_code == 200 and "trainee" in joined.json()["roles"]
            sv = await client.get(
                f"/v1/skill-versions/{DEMO_SKILL_VERSION_ID}",
                headers={"Authorization": f"Bearer {tok_anon}"},
            )
            assert sv.status_code == 200 and sv.json()["slug"] == "terminal-wiring"


async def test_traces_sse_streams_new_event() -> None:
    app = create_app()
    demo_user = CurrentUser(
        user_id=uuid4(),
        display_name="Judge",
        pseudonym="judge_sse",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    app.dependency_overrides[get_current_user] = lambda: demo_user
    session_id = UUID("40000000-0000-4000-8000-000000000001")

    async def emit_soon() -> None:
        await asyncio.sleep(0.05)
        get_telemetry_bus().record_trace(
            agent="verifier",
            kind=Kind4.verdict,
            summary="Verifier: step s3 pass (0.86)",
            scope=Scope4(session_id=session_id),
        )

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        emitter = asyncio.create_task(emit_soon())
        resp = await client.get(f"/v1/traces/stream?session_id={session_id}&max_events=1")
        await emitter
        assert resp.status_code == 200 and "Verifier: step s3 pass (0.86)" in resp.text
