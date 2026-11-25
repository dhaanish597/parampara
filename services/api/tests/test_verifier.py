"""Tests for Verifier agent exemplar, CR-008 fallback, predicate coverage, and /verify (T-020)."""

from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from types import SimpleNamespace
from typing import Any
from uuid import UUID, uuid4

import httpx
import pytest

from parampara.agents.verifier.agent import verify_step
from parampara.api.deps import ALL_DEMO_ROLES, CurrentUser, get_current_user
from parampara.api.main import create_app
from parampara.api.settings import DEFAULT_DEMO_ORG_ID, Settings, get_settings
from parampara.db.repos.skill_versions import DEMO_SKILL_VERSION_ID
from parampara.domain.generated import (
    EdgeSummary,
    Kind4,
    Scope4,
    SkillGraph,
    Status3,
    Trigger,
    VerifyRequest,
)
from parampara.telemetry.recorder import TelemetryBus

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


class _FakeModels:
    def __init__(self, responses: list[str | Exception]) -> None:
        self._responses = list(responses)
        self.models_called: list[str] = []

    def generate_content(self, **kwargs: Any) -> Any:
        self.models_called.append(str(kwargs.get("model", "")))
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        usage = SimpleNamespace(prompt_token_count=100, candidates_token_count=40)
        return SimpleNamespace(text=item, usage_metadata=usage, candidates=[])


def _req(step_id: str) -> VerifyRequest:
    return VerifyRequest(
        step_id=step_id,
        frame_jpeg_b64=base64.b64encode(b"fake-jpg").decode(),
        frame_t_ms=1500,
        edge_summary=EdgeSummary(edge_key=True, checks=["e2"]),
        trigger=Trigger.edge,
    )


async def test_verifier_agent_returns_verdict_and_logs_trace() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    step = graph.steps[1]
    preds = [
        {"predicate_id": p.id, "pass": True, "evidence": "ok"} for p in step.success_predicates
    ]
    out_json = json.dumps(
        {
            "status": "pass",
            "confidence": 0.91,
            "predicate_results": preds,
            "visible_issues": [],
            "coach_hint_hi": "बहुत बढ़िया, अगला कदम।",
        }
    )
    bus = TelemetryBus()
    client: Any = SimpleNamespace(models=_FakeModels([out_json]))
    verdict = await verify_step(
        step=step,
        req=_req(step.id),
        frame_bytes=b"fake-jpg",
        scope=Scope4(session_id=uuid4()),
        client=client,
        bus=bus,
    )
    assert verdict.status == Status3.pass_ and verdict.confidence == 0.91
    assert any(t.kind == Kind4.verdict and "s2 pass" in t.summary for t in bus.recent_traces())


async def test_verifier_cr008_falls_back_to_flash_lite_on_503() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    step = graph.steps[1]
    preds = [
        {"predicate_id": p.id, "pass": True, "evidence": "ok"} for p in step.success_predicates
    ]
    lite_json = json.dumps(
        {
            "status": "pass",
            "confidence": 0.88,
            "predicate_results": preds,
            "visible_issues": [],
            "coach_hint_hi": "ठीक है।",
        }
    )
    models = _FakeModels([RuntimeError("503 UNAVAILABLE"), lite_json])
    cfg = Settings(gemini_api_key="test", app_env="local")
    verdict = await verify_step(
        step=step,
        req=_req(step.id),
        frame_bytes=b"x",
        scope=Scope4(session_id=uuid4()),
        client=SimpleNamespace(models=models),
        bus=TelemetryBus(),
        settings=cfg,
    )
    assert verdict.status == Status3.pass_ and verdict.model == cfg.model_lite
    assert models.models_called == [cfg.model_flash, cfg.model_lite]


async def test_verifier_enforces_deterministic_predicate_coverage() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    step = graph.steps[1]
    incomplete_json = json.dumps(
        {
            "status": "pass",
            "confidence": 0.95,
            "predicate_results": [],
            "visible_issues": [],
            "coach_hint_hi": "ठीक है।",
        }
    )
    verdict = await verify_step(
        step=step,
        req=_req(step.id),
        frame_bytes=b"x",
        scope=Scope4(session_id=uuid4()),
        client=SimpleNamespace(models=_FakeModels([incomplete_json])),
        bus=TelemetryBus(),
    )
    assert verdict.status == Status3.needs_better_view
    assert "incomplete_predicate_coverage" in verdict.visible_issues
    assert len(verdict.predicate_results) == len(step.success_predicates)


async def test_verifier_agent_returns_unavailable_when_both_models_fail() -> None:
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    models = _FakeModels([TimeoutError("deadline"), TimeoutError("deadline")])
    verdict = await verify_step(
        step=graph.steps[1],
        req=_req("s2"),
        frame_bytes=b"x",
        scope=Scope4(session_id=uuid4()),
        client=SimpleNamespace(models=models),
        bus=TelemetryBus(),
    )
    assert verdict.status == Status3.unavailable


async def test_verify_endpoint_rejects_oversized_frame() -> None:
    app = create_app()
    user = CurrentUser(
        user_id=uuid4(),
        display_name="Trainee",
        pseudonym="verify_trainee",
        memberships={UUID(DEFAULT_DEMO_ORG_ID): set(ALL_DEMO_ROLES)},
    )
    app.dependency_overrides[get_settings] = lambda: Settings(
        gemini_api_key="", app_env="local", database_url=""
    )
    app.dependency_overrides[get_current_user] = lambda: user
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as c:
        start = await c.post(
            "/v1/sessions",
            json={
                "skill_version_id": str(DEMO_SKILL_VERSION_ID),
                "device": {"ua": "t", "w": 390, "h": 844},
            },
        )
        sid = start.json()["session_id"]
        big = base64.b64encode(b"0" * (601 * 1024)).decode()
        resp = await c.post(
            f"/v1/sessions/{sid}/verify",
            json={
                "step_id": "s2",
                "frame_jpeg_b64": big,
                "frame_t_ms": 1000,
                "edge_summary": {"edge_key": True, "checks": ["e2"]},
                "trigger": "edge",
            },
        )
        assert resp.status_code == 413 and resp.json()["error"]["code"] == "frame_too_large"


@pytest.mark.live
async def test_verifier_live_gemini_structured_call() -> None:
    if os.environ.get("RUN_LIVE") != "1":
        pytest.skip("Set RUN_LIVE=1 to run live Gemini tests")
    graph = SkillGraph.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))
    raw = base64.b64decode(
        "/9j/4AAQSkZJRgABAQAAAQABAAD/2wBDAAgGBgcGBQgHBwcJCQgKDBQNDAsLDBkSEw8UHRofHh0a"
        "HBwgJC4nICIsIxwcKDcpLDAxNDQ0Hyc5PTgyPC4zNDL/wAALCAABAAEBAREA/8QAFAABAAAAAAAA"
        "AAAAAAAAAAAACf/EABQQAQAAAAAAAAAAAAAAAAAAAAD/2gAIAQEAAD8AVN//2Q=="
    )
    verdict = await verify_step(
        step=graph.steps[0],
        req=VerifyRequest(
            step_id="s1",
            frame_jpeg_b64=base64.b64encode(raw).decode(),
            frame_t_ms=1000,
            edge_summary=EdgeSummary(edge_key=True, checks=[]),
            trigger=Trigger.edge,
        ),
        frame_bytes=raw,
        scope=Scope4(session_id=uuid4()),
    )
    assert verdict.status in (Status3.pass_, Status3.fail, Status3.needs_better_view)
