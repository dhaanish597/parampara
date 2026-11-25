"""Single-use Gemini Live ephemeral token minter (BUILD_PLAN 16.2 & T-003).

This is the only module besides agents/llm.py permitted to import google.genai (AGENTS.md).
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta
from typing import Any

from google import genai
from google.genai import types

from parampara.api.settings import Settings


def _build_function_declarations(live_config_dict: dict[str, Any]) -> list[Any]:
    raw_tools = live_config_dict.get("tools", [])
    tools: list[Any] = []
    for entry in raw_tools:
        decls = [
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters_json_schema=fn.get("parameters"),
            )
            for fn in entry.get("functionDeclarations", [])
        ]
        if decls:
            tools.append(types.Tool(function_declarations=decls))
    return tools


def build_sdk_live_config(live_config_dict: dict[str, Any]) -> types.LiveConnectConfig:
    """Convert the 16.3 LiveConnectConfig dict into the SDK LiveConnectConfig (single source)."""
    comp = live_config_dict.get("contextWindowCompression", {})
    sliding = comp.get("slidingWindow", {})
    resumption = live_config_dict.get("sessionResumption", {})
    voice = (
        live_config_dict.get("speechConfig", {})
        .get("voiceConfig", {})
        .get("prebuiltVoiceConfig", {})
        .get("voiceName", "Orus")
    )
    aad = live_config_dict.get("realtimeInputConfig", {}).get("automaticActivityDetection", {})
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=live_config_dict["systemInstruction"],
        tools=_build_function_declarations(live_config_dict),
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=comp.get("triggerTokens", 32000),
            sliding_window=types.SlidingWindow(target_tokens=sliding.get("targetTokens", 16000)),
        ),
        session_resumption=types.SessionResumptionConfig(handle=resumption.get("handle")),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
            )
        ),
        realtime_input_config=types.RealtimeInputConfig(
            automatic_activity_detection=types.AutomaticActivityDetection(
                disabled=bool(aad.get("disabled", False))
            )
        ),
    )


def _create_token_sync(
    *,
    api_key: str,
    model: str,
    live_config_dict: dict[str, Any],
    expires_at: datetime,
    new_session_expire: datetime,
) -> str:
    client = genai.Client(api_key=api_key, http_options=types.HttpOptions(api_version="v1alpha"))
    live_cfg = build_sdk_live_config(live_config_dict)
    tok = client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=expires_at,
            new_session_expire_time=new_session_expire,
            live_connect_constraints=types.LiveConnectConstraints(model=model, config=live_cfg),
        )
    )
    return tok.name or ""


async def mint_live_token(
    *,
    settings: Settings,
    system_instruction: str,
    live_config_dict: dict[str, Any],
    allow_offline_stub: bool = False,
) -> tuple[str, datetime]:
    """Mint a 30-min single-use v1alpha ephemeral token for MODEL_LIVE."""
    now = datetime.now(UTC)
    expires_at = now + timedelta(minutes=30)
    new_session_expire = now + timedelta(minutes=1)
    _ = system_instruction
    if not settings.gemini_api_key:
        if allow_offline_stub:
            return "auth_tokens/offline_test_token", expires_at
        raise RuntimeError("GEMINI_API_KEY is not configured")
    token_name = await asyncio.to_thread(
        _create_token_sync,
        api_key=settings.gemini_api_key,
        model=settings.model_live,
        live_config_dict=live_config_dict,
        expires_at=expires_at,
        new_session_expire=new_session_expire,
    )
    return token_name, expires_at
