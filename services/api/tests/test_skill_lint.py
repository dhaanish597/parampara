"""Tests for skill_lint deterministic semantic linter (BUILD_PLAN 10.2 & 14.6)."""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

from parampara.domain.generated import SkillGraph
from parampara.tools.skill_lint import lint_skill_graph

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


def load_fixture_dict() -> dict[str, Any]:
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))  # type: ignore[no-any-return]


def test_terminal_wiring_fixture_has_zero_lint_issues() -> None:
    graph = SkillGraph.model_validate(load_fixture_dict())
    assert lint_skill_graph(graph) == []


def test_order_gap_detected() -> None:
    raw = load_fixture_dict()
    raw["steps"][1]["order"] = 3
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    assert any(i.code == "order_gap" for i in issues)


def test_unknown_part_and_zone_detected() -> None:
    raw = load_fixture_dict()
    raw["steps"][1]["success_predicates"][0]["part_id"] = "wire_ghost"
    raw["steps"][1]["edge_checks"][0]["zone_id"] = "zone_GHOST"
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    codes = {i.code for i in issues}
    assert "unknown_part" in codes
    assert "unknown_zone" in codes


def test_critical_step_without_edge_check_detected() -> None:
    raw = load_fixture_dict()
    raw["steps"][1]["critical"] = True
    raw["steps"][1]["edge_checks"] = []
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    assert any(i.code == "critical_step_without_edge_check" for i in issues)


def test_hazard_unknown_step_and_rule_missing_fields() -> None:
    raw = load_fixture_dict()
    raw["hazards"][0]["step_id"] = "s99"
    raw["hazards"][0]["rule"]["part_id"] = None
    del raw["hazards"][0]["rule"]["part_id"]
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    codes = {i.code for i in issues}
    assert "hazard_unknown_step" in codes
    assert "rule_missing_fields" in codes


def test_segment_invalid_and_overlap_detected() -> None:
    raw = load_fixture_dict()
    raw["steps"][0]["source_segment"] = {"start_ms": 5000, "end_ms": 5000}
    raw["steps"][2]["source_segment"] = {"start_ms": 25000, "end_ms": 60000}
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    codes = {i.code for i in issues}
    assert "segment_invalid" in codes
    assert "segment_overlap" in codes


def test_missing_hindi_detected() -> None:
    raw = load_fixture_dict()
    raw["steps"][0]["instruction"]["hi"] = "Only English text here"
    issues = lint_skill_graph(SkillGraph.model_validate(raw))
    assert any(i.code == "missing_hindi" for i in issues)


def test_too_many_steps_detected() -> None:
    raw = load_fixture_dict()
    base = copy.deepcopy(raw["steps"][0])
    steps = []
    for idx in range(1, 13):
        s = copy.deepcopy(base)
        s["id"] = f"s{idx}"
        s["order"] = idx
        s["source_segment"] = {"start_ms": (idx - 1) * 1000, "end_ms": idx * 1000}
        steps.append(s)
    raw["steps"] = steps
    issues = lint_skill_graph(SkillGraph.model_validate(raw), max_steps=10)
    assert any(i.code == "too_many_steps" for i in issues)
