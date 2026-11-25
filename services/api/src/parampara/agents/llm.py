"""Single LLM gateway for all non-Live Gemini calls (BUILD_PLAN 13.1)."""

from __future__ import annotations

import asyncio
import random
import time
from dataclasses import dataclass
from typing import Any

from google import genai
from google.genai import types
from pydantic import BaseModel, ValidationError

from parampara.agents.llm_helpers import (
    Purpose,
    build_config,
    estimate_cost_usd,
    extract_audio,
    is_retryable,
    record_call,
    resolve_model,
    trace_end,
    wrap_user_text,
)
from parampara.api.settings import Settings, get_settings
from parampara.domain.generated import Kind4, Scope4
from parampara.telemetry.recorder import TelemetryBus, get_telemetry_bus

__all__ = [
    "GatewayResult",
    "Purpose",
    "SchemaViolation",
    "estimate_cost_usd",
    "generate",
    "resolve_model",
    "wrap_user_text",
]


class SchemaViolation(RuntimeError):
    """Raised when structured output still fails Pydantic validation after repair retry."""


@dataclass(frozen=True)
class GatewayResult:
    text: str | None
    parsed: Any
    audio_bytes: bytes | None
    mime_type: str | None
    model: str
    latency_ms: int
    input_tokens: int | None
    output_tokens: int | None


async def _call_with_retries(
    client: genai.Client,
    model: str,
    contents: list[Any],
    config: types.GenerateContentConfig,
    timeout_s: float,
    max_retries: int,
) -> tuple[Any, int]:
    backoffs = [1.0, 3.0]
    for attempt in range(max_retries + 1):
        t0 = time.perf_counter()
        try:
            resp = await asyncio.wait_for(
                asyncio.to_thread(
                    client.models.generate_content,
                    model=model,
                    contents=contents,
                    config=config,
                ),
                timeout=timeout_s,
            )
            return resp, int((time.perf_counter() - t0) * 1000)
        except Exception as exc:
            if attempt >= max_retries or not is_retryable(exc):
                raise
            delay = backoffs[min(attempt, len(backoffs) - 1)] + random.uniform(0, 0.25)  # noqa: S311
            await asyncio.sleep(delay)
    raise RuntimeError("Unreachable retry state")


def _finish_result(
    resp: Any,
    purpose: Purpose,
    schema: type[BaseModel] | None,
    agent: str,
    model: str,
    latency_ms: int,
    scope: Scope4,
    telemetry: TelemetryBus,
) -> GatewayResult:
    usage = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage, "prompt_token_count", None)
    out_tok = getattr(usage, "candidates_token_count", None)
    if purpose == "tts":
        audio, mime = extract_audio(resp)
        trace_end(telemetry, agent, f"{agent}: synthesized audio", scope, model, latency_ms)
        return GatewayResult(None, None, audio, mime, model, latency_ms, in_tok, out_tok)
    raw_text = getattr(resp, "text", None) or ""
    parsed = schema.model_validate_json(raw_text) if schema else None
    trace_end(telemetry, agent, f"{agent}: completed in {latency_ms} ms", scope, model, latency_ms)
    return GatewayResult(raw_text, parsed, None, None, model, latency_ms, in_tok, out_tok)


async def _run_attempt(
    sdk: genai.Client,
    model: str,
    contents: list[Any],
    gen_cfg: types.GenerateContentConfig,
    timeout_s: float,
    max_retries: int,
    agent: str,
    purpose_tag: str,
    scope: Scope4,
    telemetry: TelemetryBus,
) -> tuple[Any, int]:
    try:
        resp, ms = await _call_with_retries(sdk, model, contents, gen_cfg, timeout_s, max_retries)
    except Exception as exc:
        err_msg = f"{type(exc).__name__}: {exc}"
        record_call(telemetry, agent, model, purpose_tag, scope, 0, False, error=err_msg)
        telemetry.record_trace(
            agent=agent,
            kind=Kind4.error,
            summary=f"{agent}: failed ({err_msg[:180]})",
            scope=scope,
            model=model,
        )
        raise
    usage = getattr(resp, "usage_metadata", None)
    in_tok = getattr(usage, "prompt_token_count", None)
    out_tok = getattr(usage, "candidates_token_count", None)
    record_call(telemetry, agent, model, purpose_tag, scope, ms, True, in_tok, out_tok)
    return resp, ms


@dataclass(frozen=True)
class _CallCtx:
    sdk: genai.Client
    model: str
    gen_cfg: types.GenerateContentConfig
    timeout_s: float
    max_retries: int
    agent: str
    purpose: Purpose
    purpose_tag: str
    scope: Scope4
    telemetry: TelemetryBus


async def _execute_with_repair[T: BaseModel](
    ctx: _CallCtx, contents: list[Any], schema: type[T] | None
) -> GatewayResult:
    cur = list(contents)
    for repair_attempt in range(2):
        resp, ms = await _run_attempt(
            ctx.sdk,
            ctx.model,
            cur,
            ctx.gen_cfg,
            ctx.timeout_s,
            ctx.max_retries,
            ctx.agent,
            ctx.purpose_tag,
            ctx.scope,
            ctx.telemetry,
        )
        try:
            return _finish_result(
                resp, ctx.purpose, schema, ctx.agent, ctx.model, ms, ctx.scope, ctx.telemetry
            )
        except ValidationError as exc:
            if repair_attempt == 1:
                raise SchemaViolation(f"{ctx.agent} failed schema validation twice: {exc}") from exc
            ctx.telemetry.record_trace(
                agent=ctx.agent,
                kind=Kind4.retry,
                summary=f"{ctx.agent}: repairing invalid JSON",
                scope=ctx.scope,
                model=ctx.model,
            )
            cur = [*cur, f"Previous JSON failed validation: {exc}. Return JSON only."]
    raise SchemaViolation(f"{ctx.agent} exhausted schema repair attempts")


def _build_ctx(
    *,
    agent: str,
    purpose: Purpose,
    schema: type[BaseModel] | None,
    system: str | None,
    temperature: float,
    timeout_s: float,
    max_retries: int,
    scope: Scope4 | None,
    prompt_version: str | None,
    client: genai.Client | None,
    bus: TelemetryBus | None,
    settings: Settings | None,
) -> _CallCtx:
    cfg = settings or get_settings()
    telemetry = bus or get_telemetry_bus()
    trace_scope = scope or Scope4()
    model = resolve_model(purpose, cfg)
    purpose_tag = f"{purpose}@{prompt_version}" if prompt_version else purpose
    http_opts = types.HttpOptions(api_version="v1beta") if purpose == "tts" else None
    sdk = client or genai.Client(api_key=cfg.gemini_api_key, http_options=http_opts)
    gen_cfg = build_config(purpose, system, temperature, schema, cfg)
    return _CallCtx(
        sdk,
        model,
        gen_cfg,
        timeout_s,
        max_retries,
        agent,
        purpose,
        purpose_tag,
        trace_scope,
        telemetry,
    )


async def generate[T: BaseModel](
    *,
    agent: str,
    purpose: Purpose,
    contents: list[Any],
    response_schema: type[T] | None = None,
    system: str | None = None,
    temperature: float = 0.2,
    timeout_s: float = 30.0,
    max_retries: int = 2,
    scope: Scope4 | None = None,
    prompt_version: str | None = None,
    client: genai.Client | None = None,
    bus: TelemetryBus | None = None,
    settings: Settings | None = None,
) -> GatewayResult:
    """Route, retry, validate structured output (1 repair retry), and log telemetry."""
    ctx = _build_ctx(
        agent=agent,
        purpose=purpose,
        schema=response_schema,
        system=system,
        temperature=temperature,
        timeout_s=timeout_s,
        max_retries=max_retries,
        scope=scope,
        prompt_version=prompt_version,
        client=client,
        bus=bus,
        settings=settings,
    )
    ctx.telemetry.record_trace(
        agent=agent,
        kind=Kind4.agent_start,
        summary=f"{agent}: starting {purpose}",
        scope=ctx.scope,
        model=ctx.model,
    )
    return await _execute_with_repair(ctx, contents, response_schema)
