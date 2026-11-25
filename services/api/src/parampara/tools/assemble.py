"""Deterministic SkillGraph assembly and schema validation (BUILD_PLAN 14.2)."""

from __future__ import annotations

import copy
from typing import Any

from pydantic import ValidationError

from parampara.domain.generated import CredentialPolicy, Profile, SkillGraph

DEFAULT_PRODUCTION_POLICY = CredentialPolicy(
    profile=Profile.production,
    min_consecutive_clean_runs=3,
    mastery_threshold=0.95,
    require_exam_mode=True,
    require_cosign=True,
)


def _normalize_steps(raw_steps: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized: list[dict[str, Any]] = []
    for idx, raw in enumerate(raw_steps, start=1):
        step = copy.deepcopy(raw)
        step.setdefault("id", f"s{idx}")
        step.setdefault("order", idx)
        step.setdefault("edge_checks", [])
        step.setdefault("common_errors", [])
        step.setdefault("tips", [])
        normalized.append(step)
    return normalized


def assemble_skill_graph(
    *,
    title: dict[str, str],
    summary: dict[str, str],
    domain: str,
    parts: list[dict[str, Any]],
    zones: list[dict[str, Any]],
    steps: list[dict[str, Any]],
    hazards: list[dict[str, Any]],
    tools_required: list[dict[str, Any]] | None = None,
    credential_policy: CredentialPolicy | None = None,
) -> SkillGraph:
    """Fill missing step IDs, attach policy, and validate against SkillGraph schema."""
    policy = credential_policy or DEFAULT_PRODUCTION_POLICY
    payload: dict[str, Any] = {
        "schema_version": "1.0",
        "title": title,
        "summary": summary,
        "domain": domain,
        "parts": parts,
        "zones": zones,
        "steps": _normalize_steps(steps),
        "hazards": hazards,
        "credential_policy": policy.model_dump(mode="json"),
    }
    if tools_required is not None:
        payload["tools_required"] = tools_required
    try:
        return SkillGraph.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"Invalid SkillGraph: {exc}") from exc
