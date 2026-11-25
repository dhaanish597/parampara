"""Tests for coach builder, Live token config, and session lifecycle (BUILD_PLAN 16, T-016)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from parampara.agents.coach.builder import (
    MAX_STEPS_COMPACT_CHARS,
    build_coach_system_instruction,
    build_live_connect_config,
    format_steps_compact,
)
from parampara.agents.coach.token import build_sdk_live_config
from parampara.api.deps import ALL_DEMO_ROLES, CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.settings import DEFAULT_DEMO_ORG_ID, Settings, get_settings
from parampara.db.repos.sessions import get_session_record, record_server_vlm_key
from parampara.db.repos.skill_versions import DEMO_SKILL_VERSION_ID
from parampara.domain.generated import Mode, SessionStartResponse, SessionSummary, SkillGraph

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


def _offline_app() -> Any:
    app = create_app()
    user = CurrentUser(
        user_id=uuid4(),
        display_name="Trainee",
        pseudonym="trainee_test",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    app.dependency_overrides[get_settings] = lambda: Settings(gemini_api_key="", app_env="local")
    app.dependency_overrides[get_current_user] = lambda: user
    return app


async def _start_session(c: httpx.AsyncClient) -> SessionStartResponse:
    r = await c.post(
        "/v1/sessions",
        json={
            "skill_version_id": str(DEMO_SKILL_VERSION_ID),
            "device": {"ua": "t", "w": 390, "h": 844},
        },
    )
    assert r.status_code == 200
    return SessionStartResponse.model_validate(r.json())


def _ev(sid: str, step_id: str, typ: str, t_ms: int) -> dict[str, Any]:
    return {"session_id": sid, "step_id": step_id, "type": typ, "t_ms": t_ms, "payload": {}}


def test_coach_builder_and_live_token_config_match_16_3() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    assert len(format_steps_compact(graph)) < MAX_STEPS_COMPACT_CHARS
    prompt = build_coach_system_instruction(
        graph=graph,
        trainee_name="Pooja (demo)",
        master_name="Ramesh (demo)",
        mode=Mode.full,
        needs_help_steps=["s1", "s3"],
    )
    assert 'You are "Ustaad"' in prompt and "prompt_version:" not in prompt
    cfg_dict = build_live_connect_config(system_instruction=prompt, voice_name="Orus")
    sdk_cfg = build_sdk_live_config(cfg_dict)
    first_tool: Any = sdk_cfg.tools[0] if sdk_cfg.tools else None
    assert first_tool is not None and first_tool.function_declarations
    sdk_names = [fn.name for fn in first_tool.function_declarations]
    dict_names = [fn["name"] for fn in cfg_dict["tools"][0]["functionDeclarations"]]
    assert sdk_names == dict_names and "get_current_step" in sdk_names
    assert sdk_cfg.realtime_input_config is not None


async def test_client_completed_and_vlm_key_rejected_and_complete_idempotent() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_offline_app()), base_url="http://test"
    ) as c:
        parsed = await _start_session(c)
        sid = str(parsed.session_id)
        bad = await c.post(
            f"/v1/sessions/{sid}/events", json={"events": [_ev(sid, "s1", "vlm_key", 1000)]}
        )
        assert bad.status_code == 400
        ev = [
            _ev(sid, s.id, "completed", (i + 1) * 1000)
            for i, s in enumerate(parsed.skill_graph.steps)
        ]
        assert (await c.post(f"/v1/sessions/{sid}/events", json={"events": ev})).status_code == 200
        c1 = SessionSummary.model_validate(
            (await c.post(f"/v1/sessions/{sid}/complete", json={"status": "completed"})).json()
        )
        c2 = SessionSummary.model_validate(
            (await c.post(f"/v1/sessions/{sid}/complete", json={"status": "completed"})).json()
        )
        assert (
            c1.clean_run is False and c1.credential_eligible is False and c2.mastery == c1.mastery
        )


async def test_two_key_within_5s_clean_run_and_aborted_not_a_run() -> None:
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=_offline_app()), base_url="http://test"
    ) as c:
        s_ab = await _start_session(c)
        ab = SessionSummary.model_validate(
            (
                await c.post(f"/v1/sessions/{s_ab.session_id}/complete", json={"status": "aborted"})
            ).json()
        )
        assert ab.clean_run is False and all(m.p_learned == 0.2 for m in ab.mastery)
        s_ok = await _start_session(c)
        sid = str(s_ok.session_id)
        edges = [
            _ev(sid, s.id, "edge_key", i * 5000 + 1000)
            for i, s in enumerate(s_ok.skill_graph.steps)
        ]
        assert (
            await c.post(f"/v1/sessions/{sid}/events", json={"events": edges})
        ).status_code == 200
        ses_rec = get_session_record(UUID(sid))
        assert ses_rec is not None
        for i, step in enumerate(s_ok.skill_graph.steps):
            record_server_vlm_key(ses_rec, step.id, i * 5000 + 1500)
        ok = SessionSummary.model_validate(
            (await c.post(f"/v1/sessions/{sid}/complete", json={"status": "completed"})).json()
        )
        assert ok.clean_run is True and ok.credential_eligible is True
