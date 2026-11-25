"""Verifier agent (BUILD_PLAN 18.3, CR-008 & 31.4 LLM agent exemplar).

Exemplar LLM agent: loads versioned prompt, calls agents.llm.generate inside one 8 s
overall deadline (trying MODEL_FLASH for 4 s, then falling back to MODEL_LITE per CR-008),
enforces deterministic predicate coverage, and emits a judge-readable TraceEvent.
"""

from __future__ import annotations

import asyncio
import time
from pathlib import Path
from typing import Any

from google.genai import types
from pydantic import BaseModel, ConfigDict, Field

from parampara.agents.llm import GatewayResult, generate, wrap_user_text
from parampara.api.settings import Settings, get_settings
from parampara.domain.generated import (
    Kind4,
    PredicateResult,
    Scope4,
    Status3,
    Step,
    VerifierVerdict,
    VerifyRequest,
)
from parampara.telemetry.recorder import TelemetryBus, get_telemetry_bus
from parampara.tools.hashing import sha256_bytes

PROMPT_PATH = Path(__file__).resolve().parents[1] / "prompts" / "verifier.md"
PROMPT_VERSION = "verifier-1"
OVERALL_DEADLINE_S = 8.0
FLASH_BUDGET_S = 4.0


class VerifierModelOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Status3
    confidence: float = Field(ge=0.0, le=1.0)
    predicate_results: list[PredicateResult]
    visible_issues: list[str]
    coach_hint_hi: str


def _build_prompt_contents(
    step: Step, req: VerifyRequest, frame_bytes: bytes, ref_frame_bytes: bytes | None
) -> list[Any]:
    preds = "\n".join(
        f"- {p.id} ({p.kind.value}): {p.description}" for p in step.success_predicates
    )
    edge = wrap_user_text(
        f"edge_key={req.edge_summary.edge_key}, checks={req.edge_summary.checks}, "
        f"held_part={req.edge_summary.held_part}"
    )
    text = (
        f"Step: {step.id} — {step.title.en}\nInstruction: {step.instruction.en}\n"
        f"Success predicates:\n{preds}\nEdge summary (context only):\n{edge}"
    )
    parts: list[Any] = [text]
    if ref_frame_bytes:
        parts.extend(
            [
                "Reference photo:",
                types.Part.from_bytes(data=ref_frame_bytes, mime_type="image/jpeg"),
            ]
        )
    parts.extend(
        ["Current photo:", types.Part.from_bytes(data=frame_bytes, mime_type="image/jpeg")]
    )
    return parts


def _enforce_predicate_coverage(step: Step, out: VerifierModelOutput) -> VerifierModelOutput:
    """Deterministically verify every required step predicate was evaluated (Phase 2b)."""
    expected_ids = [p.id for p in step.success_predicates]
    seen = {pr.predicate_id for pr in out.predicate_results}
    missing = [pid for pid in expected_ids if pid not in seen]
    if not missing:
        return out
    results = list(out.predicate_results)
    for pid in missing:
        results.append(
            PredicateResult.model_validate(
                {
                    "predicate_id": pid,
                    "pass": False,
                    "evidence": "Predicate was not evaluated by verifier",
                }
            )
        )
    issues = list(out.visible_issues)
    if "incomplete_predicate_coverage" not in issues:
        issues.append("incomplete_predicate_coverage")
    status = Status3.needs_better_view if out.status == Status3.pass_ else out.status
    return out.model_copy(
        update={"status": status, "predicate_results": results, "visible_issues": issues}
    )


def _unavailable_verdict(frame_hash: str, model: str, ms: int) -> VerifierVerdict:
    return VerifierVerdict(
        status=Status3.unavailable,
        confidence=0.0,
        predicate_results=[],
        visible_issues=["verifier_unavailable"],
        coach_hint_hi="जाँच अभी उपलब्ध नहीं है, कृपया फिर से कोशिश करें।",
        frame_sha256=frame_hash,
        model=model,
        latency_ms=ms,
    )


def _trace_verdict(
    telemetry: TelemetryBus, step_id: str, verdict: VerifierVerdict, scope: Scope4
) -> None:
    sec = verdict.latency_ms / 1000.0
    summary = (
        f"Verifier: step {step_id} {verdict.status.value} ({verdict.confidence:.2f}) in {sec:.1f} s"
    )
    telemetry.record_trace(
        agent="verifier",
        kind=Kind4.verdict,
        summary=summary,
        scope=scope,
        model=verdict.model,
        latency_ms=verdict.latency_ms,
    )


def _to_verdict(out: VerifierModelOutput, frame_hash: str, model: str, ms: int) -> VerifierVerdict:
    return VerifierVerdict(
        status=out.status,
        confidence=out.confidence,
        predicate_results=out.predicate_results,
        visible_issues=out.visible_issues,
        coach_hint_hi=out.coach_hint_hi,
        frame_sha256=frame_hash,
        model=model,
        latency_ms=ms,
    )


async def _call_one(
    purpose: Any,
    timeout_s: float,
    contents: list[Any],
    system: str,
    scope: Scope4,
    client: Any | None,
    telemetry: TelemetryBus,
    cfg: Settings,
) -> GatewayResult:
    return await asyncio.wait_for(
        generate(
            agent="verifier",
            purpose=purpose,
            contents=contents,
            response_schema=VerifierModelOutput,
            system=system,
            temperature=0.1,
            timeout_s=timeout_s,
            max_retries=0,
            scope=scope,
            prompt_version=PROMPT_VERSION,
            client=client,
            bus=telemetry,
            settings=cfg,
        ),
        timeout=timeout_s,
    )


async def _call_with_fallback(
    *,
    contents: list[Any],
    system: str,
    scope: Scope4,
    client: Any | None,
    telemetry: TelemetryBus,
    cfg: Settings,
    deadline: float,
) -> GatewayResult:
    """CR-008: try MODEL_FLASH up to 4 s; fall back to MODEL_LITE with remaining 8 s budget."""
    flash_budget = max(0.1, min(FLASH_BUDGET_S, deadline - time.monotonic()))
    try:
        return await _call_one(
            "verify", flash_budget, contents, system, scope, client, telemetry, cfg
        )
    except Exception:
        remaining = deadline - time.monotonic()
        if remaining <= 0.2:
            raise
        return await _call_one(
            "text_small", remaining, contents, system, scope, client, telemetry, cfg
        )


async def verify_step(
    *,
    step: Step,
    req: VerifyRequest,
    frame_bytes: bytes,
    scope: Scope4,
    ref_frame_bytes: bytes | None = None,
    client: Any | None = None,
    bus: TelemetryBus | None = None,
    settings: Settings | None = None,
) -> VerifierVerdict:
    """Verify one step from a single JPEG frame within one 8 s overall deadline (CR-008)."""
    cfg, telemetry = settings or get_settings(), bus or get_telemetry_bus()
    frame_hash = sha256_bytes(frame_bytes)
    contents = _build_prompt_contents(step, req, frame_bytes, ref_frame_bytes)
    system = PROMPT_PATH.read_text(encoding="utf-8")
    t0 = time.monotonic()
    deadline = t0 + OVERALL_DEADLINE_S
    try:
        res = await _call_with_fallback(
            contents=contents,
            system=system,
            scope=scope,
            client=client,
            telemetry=telemetry,
            cfg=cfg,
            deadline=deadline,
        )
        checked = _enforce_predicate_coverage(step, res.parsed)
        total_ms = int((time.monotonic() - t0) * 1000)
        verdict = _to_verdict(checked, frame_hash, res.model, total_ms)
    except Exception:
        total_ms = int((time.monotonic() - t0) * 1000)
        verdict = _unavailable_verdict(frame_hash, cfg.model_flash, total_ms)
    _trace_verdict(telemetry, step.id, verdict, scope)
    return verdict
