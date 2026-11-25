"""Bayesian Knowledge Tracing, coaching mode selection, and eligibility (BUILD_PLAN 19)."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from parampara.domain.generated import CredentialPolicy, Mode, Severity2, StepOutcome

P_L0 = 0.2
P_T = 0.15
P_S = 0.10
P_G = 0.20


@dataclass(frozen=True)
class RunRecord:
    clean_run: bool
    mode: str


def bkt_update(p_learned: float, correct: bool) -> float:
    """Update P(L) for one step observation per BUILD_PLAN 19.1."""
    if correct:
        num = p_learned * (1.0 - P_S)
        den = num + (1.0 - p_learned) * P_G
    else:
        num = p_learned * P_S
        den = num + (1.0 - p_learned) * (1.0 - P_G)
    posterior = num / den if den > 0 else p_learned
    return posterior + (1.0 - posterior) * P_T


def step_is_correct(outcome: StepOutcome) -> bool:
    """A step observation is correct iff completed, two_key, no errors, hint_level_max <= 1."""
    if not outcome.completed or not outcome.two_key:
        return False
    if outcome.hint_level_max.value > 1:
        return False
    return len(outcome.errors) == 0


def is_clean_run(outcomes: Sequence[StepOutcome], expected_step_count: int) -> bool:
    """Clean run per BUILD_PLAN 3: all steps completed & two-key, no major/critical, hints <= 1."""
    if len(outcomes) < expected_step_count:
        return False
    for step in outcomes:
        if not step.completed or not step.two_key:
            return False
        if step.hint_level_max.value > 1:
            return False
        if any(e.severity in (Severity2.major, Severity2.critical) for e in step.errors):
            return False
    return True


def select_mode(
    p_by_step: Mapping[str, float],
    step_ids: Sequence[str],
    mastery_threshold: float,
) -> tuple[Mode, list[str]]:
    """Select coaching mode and needs_help_steps per BUILD_PLAN 19.2."""
    if not step_ids:
        return Mode.full, []
    values = {s: p_by_step.get(s, P_L0) for s in step_ids}
    min_p = min(values.values())
    needs_help = [s for s in step_ids if values[s] < 0.5]
    if min_p < 0.5:
        return Mode.full, needs_help
    if min_p >= mastery_threshold:
        return Mode.exam, needs_help
    if min_p < 0.8:
        return Mode.hint, needs_help
    return Mode.watch, needs_help


def check_credential_eligibility(
    *,
    p_by_step: Mapping[str, float],
    step_ids: Sequence[str],
    recent_runs: Sequence[RunRecord],
    policy: CredentialPolicy,
) -> tuple[bool, list[str]]:
    """Evaluate BUILD_PLAN 19.3 criteria 1-3 and return (eligible, unmet_reasons)."""
    reasons: list[str] = []
    min_p = min((p_by_step.get(s, P_L0) for s in step_ids), default=0.0)
    if min_p < policy.mastery_threshold:
        reasons.append(f"min_mastery {min_p:.2f} < {policy.mastery_threshold:.2f}")
    needed = policy.min_consecutive_clean_runs
    tail = list(recent_runs[-needed:]) if needed > 0 else []
    if len(tail) < needed or not all(r.clean_run for r in tail):
        reasons.append(f"requires {needed} consecutive clean runs")
    if policy.require_exam_mode and (len(tail) < needed or not all(r.mode == "exam" for r in tail)):
        reasons.append("requires clean runs in exam mode")
    return len(reasons) == 0, reasons
