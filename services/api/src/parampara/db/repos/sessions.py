"""Session state store and mastery summary builder (BUILD_PLAN 12.2, 16, 19)."""

from __future__ import annotations

from dataclasses import dataclass, field
from uuid import UUID

from parampara.domain.generated import (
    Assurance,
    Calibration,
    Coach,
    EdgeFps,
    Error1,
    HintLevelMax,
    MasteryItem,
    Mode,
    SessionSummary,
    Severity2,
    SkillGraph,
    Status2,
    StepEvent,
    StepOutcome,
    Type,
)
from parampara.tools.bkt import (
    P_L0,
    RunRecord,
    bkt_update,
    check_credential_eligibility,
    is_clean_run,
    select_mode,
    step_is_correct,
)

TWO_KEY_WINDOW_MS = 5000


@dataclass
class SessionRecord:
    id: UUID
    org_id: UUID
    skill_version_id: UUID
    trainee_user_id: UUID
    mode: Mode
    graph: SkillGraph
    status: str = "active"
    calibration: Calibration | None = None
    events: list[StepEvent] = field(default_factory=list)
    server_vlm_keys: dict[str, list[int]] = field(default_factory=dict)
    summary: SessionSummary | None = None
    clip_id: UUID | None = None


_SESSIONS: dict[UUID, SessionRecord] = {}
_MASTERY: dict[tuple[UUID, UUID], dict[str, float]] = {}
_RUNS: dict[tuple[UUID, UUID], list[RunRecord]] = {}


def save_session(record: SessionRecord) -> None:
    _SESSIONS[record.id] = record


def get_session_record(session_id: UUID) -> SessionRecord | None:
    return _SESSIONS.get(session_id)


def get_user_mastery(user_id: UUID, skill_version_id: UUID) -> dict[str, float]:
    return _MASTERY.get((user_id, skill_version_id), {})


def record_server_vlm_key(ses: SessionRecord, step_id: str, frame_t_ms: int) -> None:
    """Record a server-verified VLM pass key written exclusively by POST /verify."""
    ses.server_vlm_keys.setdefault(step_id, []).append(frame_t_ms)


def _has_two_key_within_window(edge_times: list[int], vlm_times: list[int]) -> bool:
    return any(abs(et - vt) <= TWO_KEY_WINDOW_MS for et in edge_times for vt in vlm_times)


def _step_assurance(edge_events: list[StepEvent], vlm_times: list[int], two_key: bool) -> Assurance:
    if not two_key:
        return Assurance.none
    single_match = any(
        e.payload.get("assurance") == "single" and abs(e.t_ms - vt) <= TWO_KEY_WINDOW_MS
        for e in edge_events
        for vt in vlm_times
    )
    return Assurance.single if single_match else Assurance.two_key


def build_step_outcomes(
    graph: SkillGraph,
    events: list[StepEvent],
    server_vlm_keys: dict[str, list[int]],
) -> list[StepOutcome]:
    outcomes: list[StepOutcome] = []
    for step in sorted(graph.steps, key=lambda s: s.order):
        se = [e for e in events if e.step_id == step.id]
        edge_events = [e for e in se if e.type == Type.edge_key]
        vlm_times = server_vlm_keys.get(step.id, [])
        # No LLM verdict alone completes a step (AGENTS.md): a step needs both keys.
        two_key = _has_two_key_within_window([e.t_ms for e in edge_events], vlm_times)
        max_hint = max(
            (int(e.payload.get("level", 0)) for e in se if e.type == Type.hint), default=0
        )
        errors = [
            Error1(
                error_id=str(e.payload.get("error_id")) if e.payload.get("error_id") else None,
                severity=Severity2(str(e.payload.get("severity", "major"))),
                t_ms=e.t_ms,
            )
            for e in se
            if e.type in (Type.risk, Type.failed)
        ]
        times = [e.t_ms for e in se]
        dur = max(times) - min(times) if len(times) >= 2 else 0
        outcomes.append(
            StepOutcome(
                step_id=step.id,
                completed=two_key,
                two_key=two_key,
                assurance=_step_assurance(edge_events, vlm_times, two_key),
                hint_level_max=HintLevelMax(min(3, max(0, max_hint))),
                errors=errors,
                duration_ms=max(0, dur),
            )
        )
    return outcomes


def _update_mastery_map(
    outcomes: list[StepOutcome],
    reached: set[str | None],
    existing_mastery: dict[str, float],
) -> tuple[dict[str, float], dict[str, float]]:
    m_map = dict(existing_mastery)
    updates: dict[str, float] = {}
    # 19.1: completed and aborted sessions both observe every reached step.
    for out in outcomes:
        if out.step_id in reached:
            new_p = bkt_update(m_map.get(out.step_id, P_L0), step_is_correct(out))
            m_map[out.step_id] = new_p
            updates[out.step_id] = new_p
    return m_map, updates


def compute_session_summary(
    ses: SessionRecord,
    status: Status2,
    existing_mastery: dict[str, float],
    prior_runs: list[RunRecord],
    *,
    coach: Coach = Coach.live,
    edge_fps: float | None = None,
) -> tuple[SessionSummary, dict[str, float]]:
    """Pure BKT + eligibility summary calculator shared by DB and in-memory paths."""
    outcomes = build_step_outcomes(ses.graph, ses.events, ses.server_vlm_keys)
    reached: set[str | None] = {e.step_id for e in ses.events if e.step_id}
    m_map, updates = _update_mastery_map(outcomes, reached, existing_mastery)
    # Glossary: a run is a completed session; aborted sessions never join the streak.
    clean = status == Status2.completed and is_clean_run(outcomes, len(ses.graph.steps))
    runs = list(prior_runs)
    if status == Status2.completed:
        runs.append(RunRecord(clean_run=clean, mode=ses.mode.value))
    step_ids = [s.id for s in ses.graph.steps]
    next_mode, _ = select_mode(m_map, step_ids, ses.graph.credential_policy.mastery_threshold)
    eligible, _ = check_credential_eligibility(
        p_by_step=m_map, step_ids=step_ids, recent_runs=runs, policy=ses.graph.credential_policy
    )
    summary = SessionSummary(
        session_id=ses.id,
        status=status,
        mode=ses.mode.value,
        coach=coach,
        edge_fps=EdgeFps(edge_fps) if edge_fps is not None else None,
        steps=outcomes,
        clean_run=clean,
        total_ms=max((e.t_ms for e in ses.events), default=0),
        mastery=[MasteryItem(step_id=s, p_learned=m_map.get(s, P_L0)) for s in step_ids],
        next_mode=next_mode.value,
        credential_eligible=eligible,
        policy=ses.graph.credential_policy,
    )
    return summary, updates


def finalize_mastery_and_summary(
    ses: SessionRecord,
    status: Status2,
    *,
    coach: Coach = Coach.live,
    edge_fps: float | None = None,
) -> SessionSummary:
    if ses.summary is not None:
        return ses.summary
    key = (ses.trainee_user_id, ses.skill_version_id)
    m_map = _MASTERY.setdefault(key, {})
    runs = _RUNS.setdefault(key, [])
    summary, updates = compute_session_summary(
        ses, status, m_map, runs, coach=coach, edge_fps=edge_fps
    )
    m_map.update(updates)
    if status == Status2.completed:
        runs.append(RunRecord(clean_run=summary.clean_run, mode=ses.mode.value))
    ses.summary = summary
    return summary
