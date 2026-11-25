"""Tests for SkillGraph assembly and schema validation helper (BUILD_PLAN 14.2)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from parampara.domain.generated import CredentialPolicy, Profile
from parampara.tools.assemble import assemble_skill_graph

FIXTURE_PATH = (
    Path(__file__).resolve().parents[3]
    / "contracts"
    / "fixtures"
    / "skill-graph.terminal-wiring.json"
)


def test_assemble_fills_ids_and_validates_schema() -> None:
    raw: dict[str, Any] = json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))
    for step in raw["steps"]:
        step.pop("id", None)
    policy = CredentialPolicy(
        profile=Profile.demo,
        min_consecutive_clean_runs=1,
        mastery_threshold=0.5,
        require_exam_mode=False,
        require_cosign=True,
    )
    graph = assemble_skill_graph(
        title=raw["title"],
        summary=raw["summary"],
        domain=raw["domain"],
        parts=raw["parts"],
        zones=raw["zones"],
        steps=raw["steps"],
        hazards=raw["hazards"],
        tools_required=raw.get("tools_required", []),
        credential_policy=policy,
    )
    assert [s.id for s in graph.steps] == ["s1", "s2", "s3", "s4", "s5", "s6"]
    assert graph.credential_policy.profile == Profile.demo


def test_assemble_rejects_invalid_graph() -> None:
    with pytest.raises(ValueError):
        assemble_skill_graph(
            title={"en": "Bad", "hi": "गलत"},
            summary={"en": "Too few steps", "hi": "कम कदम"},
            domain="electrical",
            parts=[],
            zones=[],
            steps=[],
            hazards=[],
        )
