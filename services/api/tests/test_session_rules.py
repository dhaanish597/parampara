"""Server-side step and run rules from the batch 1 review follow-up (BUILD_PLAN 18.1, 19.1)."""

from __future__ import annotations

import json
from pathlib import Path
from uuid import uuid4

from parampara.db.repos.sessions import (
    SessionRecord,
    build_step_outcomes,
    finalize_mastery_and_summary,
    get_user_mastery,
    record_server_vlm_key,
)
from parampara.domain.generated import Mode, SkillGraph, Status2, StepEvent, Type
from parampara.tools.bkt import P_L0

FIXTURE = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


def _graph(*, drop_edge_checks_on: str | None = None) -> SkillGraph:
    raw = json.loads(FIXTURE.read_text(encoding="utf-8"))
    for step in raw["steps"]:
        if step["id"] == drop_edge_checks_on:
            step["edge_checks"] = []
    return SkillGraph.model_validate(raw)


def _session(graph: SkillGraph) -> SessionRecord:
    return SessionRecord(uuid4(), uuid4(), uuid4(), uuid4(), Mode.full, graph)


def _event(ses: SessionRecord, step_id: str, typ: Type, t_ms: int) -> StepEvent:
    return StepEvent(session_id=ses.id, step_id=step_id, type=typ, t_ms=t_ms, payload={})


def test_step_without_edge_checks_never_completes_on_the_vlm_key_alone() -> None:
    graph = _graph(drop_edge_checks_on="s1")
    ses = _session(graph)
    record_server_vlm_key(ses, "s1", 1000)

    outcome = build_step_outcomes(graph, ses.events, ses.server_vlm_keys)[0]

    assert outcome.step_id == "s1"
    assert outcome.completed is False
    assert outcome.two_key is False


def test_aborted_session_updates_mastery_for_reached_steps_but_is_not_a_run() -> None:
    graph = _graph()
    ses = _session(graph)
    ses.events.append(_event(ses, "s1", Type.started, 0))

    summary = finalize_mastery_and_summary(ses, Status2.aborted)

    mastery = get_user_mastery(ses.trainee_user_id, ses.skill_version_id)
    assert mastery["s1"] != P_L0
    assert "s2" not in mastery
    assert summary.clean_run is False
    assert summary.credential_eligible is False
