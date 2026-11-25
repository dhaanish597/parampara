"""Deterministic semantic linter for SkillGraph (BUILD_PLAN 10.2 & 14.6)."""

from __future__ import annotations

import re

from parampara.domain.generated import Hazard, Kind2, LintIssue, SkillGraph, Step

DEVANAGARI_RE = re.compile(r"[\u0900-\u097F]")
DEFAULT_MAX_STEPS = 12


def _issue(path: str, code: str, message: str) -> LintIssue:
    return LintIssue(path=path, code=code, message=message)


def _check_part_zone(
    path: str,
    part_id: str | None,
    zone_id: str | None,
    part_ids: set[str],
    zone_ids: set[str],
) -> list[LintIssue]:
    out: list[LintIssue] = []
    if part_id and part_id not in part_ids:
        out.append(_issue(f"{path}.part_id", "unknown_part", f"Unknown part_id: {part_id}"))
    if zone_id and zone_id not in zone_ids:
        out.append(_issue(f"{path}.zone_id", "unknown_zone", f"Unknown zone_id: {zone_id}"))
    return out


def _check_step(step: Step, idx: int, part_ids: set[str], zone_ids: set[str]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    prefix = f"steps[{idx}]"
    for i, pred in enumerate(step.success_predicates):
        p = f"{prefix}.success_predicates[{i}]"
        issues.extend(_check_part_zone(p, pred.part_id, pred.zone_id, part_ids, zone_ids))
    for i, chk in enumerate(step.edge_checks):
        p = f"{prefix}.edge_checks[{i}]"
        issues.extend(_check_part_zone(p, chk.part_id, chk.zone_id, part_ids, zone_ids))
    if not step.edge_checks:
        issues.append(
            _issue(
                f"{prefix}.edge_checks",
                "step_without_edge_check",
                f"Step {step.id} requires at least one edge_check (CR-009)",
            )
        )
    if step.critical and not step.edge_checks:
        issues.append(
            _issue(
                f"{prefix}.edge_checks",
                "critical_step_without_edge_check",
                f"Critical step {step.id} requires at least one edge_check",
            )
        )
    if not DEVANAGARI_RE.search(step.instruction.hi):
        issues.append(
            _issue(
                f"{prefix}.instruction.hi",
                "missing_hindi",
                f"Step {step.id} instruction.hi must contain Devanagari text",
            )
        )
    return issues


def _check_segments(steps: list[Step]) -> list[LintIssue]:
    issues: list[LintIssue] = []
    seen: list[tuple[int, int, int]] = []
    for idx, step in enumerate(steps):
        seg = step.source_segment
        if seg.end_ms <= seg.start_ms:
            issues.append(_issue(f"steps[{idx}].source_segment", "segment_invalid", "end <= start"))
            continue
        for prev_idx, p_start, p_end in seen:
            if seg.start_ms < p_end and p_start < seg.end_ms:
                msg = f"Segment overlaps with steps[{prev_idx}]"
                issues.append(_issue(f"steps[{idx}].source_segment", "segment_overlap", msg))
                break
        seen.append((idx, seg.start_ms, seg.end_ms))
    return issues


def _check_hazard(
    hazard: Hazard,
    idx: int,
    step_ids: set[str],
    part_ids: set[str],
    zone_ids: set[str],
) -> list[LintIssue]:
    issues: list[LintIssue] = []
    prefix = f"hazards[{idx}]"
    if hazard.step_id not in step_ids:
        issues.append(_issue(f"{prefix}.step_id", "hazard_unknown_step", hazard.step_id))
    if hazard.rule.kind == Kind2.wrong_part_near_zone:
        if not hazard.rule.part_id or not hazard.rule.forbidden_zone_id:
            msg = "wrong_part_near_zone requires part_id and forbidden_zone_id"
            issues.append(_issue(f"{prefix}.rule", "rule_missing_fields", msg))
        else:
            if hazard.rule.part_id not in part_ids:
                issues.append(_issue(f"{prefix}.rule.part_id", "unknown_part", hazard.rule.part_id))
            if hazard.rule.forbidden_zone_id not in zone_ids:
                z = hazard.rule.forbidden_zone_id
                issues.append(_issue(f"{prefix}.rule.forbidden_zone_id", "unknown_zone", z))
    return issues


def lint_skill_graph(graph: SkillGraph, *, max_steps: int = DEFAULT_MAX_STEPS) -> list[LintIssue]:
    """Run all deterministic semantic rules from BUILD_PLAN 10.2 & 14.6."""
    issues: list[LintIssue] = []
    part_ids = {p.id for p in graph.parts}
    zone_ids = {z.id for z in graph.zones}
    step_ids = {s.id for s in graph.steps}
    if len(graph.steps) > max_steps:
        issues.append(_issue("steps", "too_many_steps", f"{len(graph.steps)} > {max_steps}"))
    expected = list(range(1, len(graph.steps) + 1))
    if [s.order for s in graph.steps] != expected:
        issues.append(_issue("steps", "order_gap", f"Expected orders {expected}"))
    for idx, step in enumerate(graph.steps):
        issues.extend(_check_step(step, idx, part_ids, zone_ids))
    issues.extend(_check_segments(graph.steps))
    for idx, hazard in enumerate(graph.hazards):
        issues.extend(_check_hazard(hazard, idx, step_ids, part_ids, zone_ids))
    return issues
