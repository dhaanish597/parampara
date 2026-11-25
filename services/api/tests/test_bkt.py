"""Tests for BKT mastery, mode selection, and credential eligibility (BUILD_PLAN 19)."""

from __future__ import annotations

import pytest

from parampara.domain.generated import (
    Assurance,
    CredentialPolicy,
    Error1,
    HintLevelMax,
    Mode,
    Profile,
    Severity2,
    StepOutcome,
)
from parampara.tools.bkt import (
    P_L0,
    RunRecord,
    bkt_update,
    check_credential_eligibility,
    is_clean_run,
    select_mode,
)


def _outcome(
    step_id: str,
    *,
    completed: bool = True,
    two_key: bool = True,
    hint: HintLevelMax = HintLevelMax.int_0,
    errors: list[Error1] | None = None,
) -> StepOutcome:
    return StepOutcome(
        step_id=step_id,
        completed=completed,
        two_key=two_key,
        assurance=Assurance.two_key if (completed and two_key) else Assurance.none,
        hint_level_max=hint,
        errors=errors or [],
        duration_ms=5000,
    )


def test_bkt_update_matches_hand_computed_values() -> None:
    # Hand-computed from BUILD_PLAN 19.1 with P_L0=0.2, P_T=0.15, P_S=0.10, P_G=0.20:
    # Correct: p = 0.2*0.9 / (0.18 + 0.8*0.2) = 0.18 / 0.34 = 0.52941176
    # p_next = 0.52941176 + 0.47058824 * 0.15 = 0.60000000
    assert bkt_update(P_L0, True) == pytest.approx(0.6, abs=1e-6)
    # Incorrect: p = 0.2*0.1 / (0.02 + 0.8*0.8) = 0.02 / 0.66 = 0.03030303
    # p_next = 0.03030303 + 0.96969697 * 0.15 = 0.17575758
    assert bkt_update(P_L0, False) == pytest.approx(0.17575758, abs=1e-6)


def test_mode_selection_thresholds_and_needs_help() -> None:
    steps = ["s1", "s2"]
    assert select_mode({"s1": 0.2, "s2": 0.9}, steps, 0.95) == (Mode.full, ["s1"])
    assert select_mode({"s1": 0.6, "s2": 0.9}, steps, 0.95) == (Mode.hint, [])
    assert select_mode({"s1": 0.85, "s2": 0.9}, steps, 0.95) == (Mode.watch, [])
    assert select_mode({"s1": 0.95, "s2": 0.98}, steps, 0.95) == (Mode.exam, [])
    # Demo threshold 0.5 reaches exam at 0.5
    assert select_mode({"s1": 0.6, "s2": 0.6}, steps, 0.5) == (Mode.exam, [])


def test_clean_run_and_credential_eligibility() -> None:
    clean = [_outcome("s1"), _outcome("s2", hint=HintLevelMax.int_1)]
    assert is_clean_run(clean, 2) is True
    major_err = [
        _outcome("s1"),
        _outcome("s2", errors=[Error1(error_id="m1", severity=Severity2.critical, t_ms=1000)]),
    ]
    assert is_clean_run(major_err, 2) is False

    demo_policy = CredentialPolicy(
        profile=Profile.demo,
        min_consecutive_clean_runs=1,
        mastery_threshold=0.5,
        require_exam_mode=False,
        require_cosign=True,
    )
    ok, reasons = check_credential_eligibility(
        p_by_step={"s1": 0.6, "s2": 0.6},
        step_ids=["s1", "s2"],
        recent_runs=[RunRecord(clean_run=True, mode="full")],
        policy=demo_policy,
    )
    assert ok is True and reasons == []

    prod_policy = CredentialPolicy(
        profile=Profile.production,
        min_consecutive_clean_runs=3,
        mastery_threshold=0.95,
        require_exam_mode=True,
        require_cosign=True,
    )
    ok2, reasons2 = check_credential_eligibility(
        p_by_step={"s1": 0.6, "s2": 0.6},
        step_ids=["s1", "s2"],
        recent_runs=[RunRecord(clean_run=True, mode="full")],
        policy=prod_policy,
    )
    assert ok2 is False and len(reasons2) == 3
