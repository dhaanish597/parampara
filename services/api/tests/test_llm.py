"""Tests for LLM gateway routing, schema repair retry, telemetry, and settings (BUILD_PLAN 13.1)."""

from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest
from pydantic import BaseModel, ConfigDict, ValidationError

from parampara.agents.llm import SchemaViolation, generate, resolve_model, wrap_user_text
from parampara.agents.llm_helpers import build_config
from parampara.api.settings import Settings
from parampara.domain.generated import Kind4
from parampara.telemetry.recorder import TelemetryBus


class SampleOut(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ok: bool


class FakeModels:
    def __init__(self, responses: list[Any]) -> None:
        self._responses = list(responses)
        self.calls = 0
        self.last_config: Any = None

    def generate_content(self, **kwargs: Any) -> Any:
        self.calls += 1
        self.last_config = kwargs.get("config")
        item = self._responses.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _fake_resp(text: str) -> Any:
    usage = SimpleNamespace(prompt_token_count=10, candidates_token_count=5)
    return SimpleNamespace(text=text, usage_metadata=usage, candidates=[])


def test_model_routing_and_user_text_wrapper() -> None:
    cfg = Settings()
    assert resolve_model("verify", cfg) == cfg.model_flash
    assert resolve_model("text_small", cfg) == cfg.model_lite
    assert resolve_model("tts", cfg) == cfg.model_tts
    assert "<<<USER_TEXT" in wrap_user_text("ignore instructions")


def test_build_config_uses_response_json_schema_not_response_schema() -> None:
    cfg = Settings()
    gen_cfg = build_config("verify", "sys", 0.2, SampleOut, cfg)
    assert gen_cfg.response_schema is None
    assert gen_cfg.response_json_schema == SampleOut.model_json_schema()


def test_issuer_seed_never_defaults_to_zero_and_fails_in_prod() -> None:
    local_cfg = Settings(app_env="local", issuer_ed25519_seed_b64="")
    assert base64.b64decode(local_cfg.issuer_ed25519_seed_b64) != bytes(32)
    with pytest.raises(ValidationError):
        Settings(app_env="production", issuer_ed25519_seed_b64="")
    with pytest.raises(ValidationError):
        Settings(app_env="production", issuer_ed25519_seed_b64=base64.b64encode(bytes(32)).decode())


async def test_generate_repairs_invalid_json_once_and_logs_telemetry() -> None:
    models = FakeModels([_fake_resp("not-json"), _fake_resp('{"ok": true}')])
    client: Any = SimpleNamespace(models=models)
    bus = TelemetryBus()
    res = await generate(
        agent="verifier",
        purpose="verify",
        contents=["check"],
        response_schema=SampleOut,
        client=client,
        bus=bus,
        prompt_version="verifier-1",
    )
    assert res.parsed == SampleOut(ok=True)
    assert models.calls == 2
    kinds = [e.kind for e in bus.recent_traces()]
    assert Kind4.agent_start in kinds and Kind4.retry in kinds and Kind4.agent_end in kinds
    assert len(bus.usage_summary()) == 1


async def test_generate_logs_exception_message_in_error_trace() -> None:
    models = FakeModels([RuntimeError("400 Unknown name additional_properties")])
    client: Any = SimpleNamespace(models=models)
    bus = TelemetryBus()
    with pytest.raises(RuntimeError):
        await generate(
            agent="verifier",
            purpose="verify",
            contents=["check"],
            response_schema=SampleOut,
            client=client,
            bus=bus,
            max_retries=0,
        )
    err_traces = [e for e in bus.recent_traces() if e.kind == Kind4.error]
    assert err_traces and "additional_properties" in err_traces[0].summary


async def test_generate_raises_schema_violation_after_second_failure() -> None:
    models = FakeModels([_fake_resp("bad"), _fake_resp("still-bad")])
    client: Any = SimpleNamespace(models=models)
    with pytest.raises(SchemaViolation):
        await generate(
            agent="verifier",
            purpose="verify",
            contents=["check"],
            response_schema=SampleOut,
            client=client,
            bus=TelemetryBus(),
        )
