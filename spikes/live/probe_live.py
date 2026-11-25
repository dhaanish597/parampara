"""T-003 Live API spike: verify ephemeral token, audio+video, tool call, Hindi reply, and session resumption."""

from __future__ import annotations

import asyncio
import datetime
import os
import struct
import time
import zlib
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "services" / "api" / ".env")

LIVE_MODEL = "gemini-3.8-live"
VOICE_NAME = "Orus"


def make_tiny_png() -> tuple[bytes, str]:
    """Generate a minimal 64x64 solid-red PNG without external image deps."""
    w, h = 64, 64
    raw = b"".join(b"\x00" + b"\xc8\x20\x20" * w for _ in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", zlib.crc32(tag + data))

    png = (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )
    return png, "image/png"


def build_live_config(handle: str | None = None) -> types.LiveConnectConfig:
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_current_step",
                description="Returns the active step and coaching mode.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            )
        ]
    )
    return types.LiveConnectConfig(
        response_modalities=[types.Modality.AUDIO],
        system_instruction=(
            'You are "Ustaad", a patient Hindi workshop coach. '
            "Call get_current_step first, then greet the trainee in one short Hindi sentence."
        ),
        tools=[tool],
        input_audio_transcription=types.AudioTranscriptionConfig(),
        output_audio_transcription=types.AudioTranscriptionConfig(),
        context_window_compression=types.ContextWindowCompressionConfig(
            trigger_tokens=32000,
            sliding_window=types.SlidingWindow(target_tokens=16000),
        ),
        session_resumption=types.SessionResumptionConfig(handle=handle),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
    )


async def test_live_session(api_key: str) -> None:
    now = datetime.datetime.now(datetime.timezone.utc)
    live_config = build_live_config(handle=None)

    token_client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
    t0 = time.perf_counter()
    token = token_client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=now + datetime.timedelta(minutes=30),
            new_session_expire_time=now + datetime.timedelta(minutes=1),
            live_connect_constraints=types.LiveConnectConstraints(
                model=LIVE_MODEL,
                config=live_config,
            ),
        )
    )
    mint_ms = int((time.perf_counter() - t0) * 1000)
    print(f"TOKEN OK api_version=v1alpha mint_ms={mint_ms} prefix={token.name[:16]}...", flush=True)

    ephemeral_client = genai.Client(api_key=token.name, http_options={"api_version": "v1alpha"})
    t_conn = time.perf_counter()
    resumption_handle: str | None = None

    async with ephemeral_client.aio.live.connect(model=LIVE_MODEL, config=live_config) as session:
        conn_ms = int((time.perf_counter() - t_conn) * 1000)
        print(f"LIVE CONNECTED conn_ms={conn_ms}", flush=True)

        img_bytes, img_mime = make_tiny_png()
        await session.send_realtime_input(media=types.Blob(data=img_bytes, mime_type=img_mime))
        t_turn = time.perf_counter()
        await session.send_client_content(
            turns=types.Content(
                role="user",
                parts=[types.Part(text="नमस्ते उस्ताद, शुरू करें।")],
            ),
            turn_complete=True,
        )

        audio_bytes = 0
        transcript_parts: list[str] = []
        tool_called = False
        first_audio_ms: int | None = None
        t_after_tool: float | None = None

        async def wait_first_audio() -> None:
            nonlocal resumption_handle, audio_bytes, tool_called, first_audio_ms, t_after_tool
            while True:
                async for msg in session.receive():
                    if msg.session_resumption_update and msg.session_resumption_update.new_handle:
                        resumption_handle = msg.session_resumption_update.new_handle
                        print(
                            f"RESUMPTION handle_len={len(resumption_handle)} "
                            f"resumable={msg.session_resumption_update.resumable}",
                            flush=True,
                        )
                    if msg.tool_call and msg.tool_call.function_calls:
                        for fc in msg.tool_call.function_calls:
                            tool_ms = int((time.perf_counter() - t_turn) * 1000)
                            print(f"TOOL_CALL name={fc.name} latency_ms={tool_ms}", flush=True)
                            tool_called = True
                            t_after_tool = time.perf_counter()
                            await session.send_tool_response(
                                function_responses=[
                                    types.FunctionResponse(
                                        id=fc.id,
                                        name=fc.name,
                                        response={
                                            "step_id": "s1",
                                            "title_hi": "तार और फेरूल जाँचें",
                                            "mode": "full",
                                            "verified_steps": [],
                                        },
                                    )
                                ]
                            )
                    if msg.server_content:
                        sc = msg.server_content
                        if sc.output_transcription and sc.output_transcription.text:
                            transcript_parts.append(sc.output_transcription.text)
                        if sc.model_turn and sc.model_turn.parts:
                            for p in sc.model_turn.parts:
                                if p.inline_data and p.inline_data.data:
                                    if first_audio_ms is None:
                                        base = t_after_tool or t_turn
                                        first_audio_ms = int((time.perf_counter() - base) * 1000)
                                    audio_bytes += len(p.inline_data.data)
                        if sc.turn_complete and audio_bytes > 0:
                            total_ms = int((time.perf_counter() - t_turn) * 1000)
                            print(
                                f"AUDIO_TURN_COMPLETE first_audio_ms={first_audio_ms} "
                                f"total_ms={total_ms} audio_bytes={audio_bytes} "
                                f"tool_called={tool_called}",
                                flush=True,
                            )
                            print(f"TRANSCRIPT_HI: {''.join(transcript_parts).strip()}", flush=True)
                            return

        await asyncio.wait_for(wait_first_audio(), timeout=20)

    if resumption_handle:
        resume_config = build_live_config(handle=resumption_handle)
        t_res = time.perf_counter()
        resume_client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
        async with resume_client.aio.live.connect(model=LIVE_MODEL, config=resume_config) as s2:
            res_ms = int((time.perf_counter() - t_res) * 1000)
            print(f"RESUME_CONNECTED ms={res_ms}", flush=True)
            t_r = time.perf_counter()
            await s2.send_client_content(
                turns=types.Content(
                    role="user",
                    parts=[types.Part(text="हम किस कदम पर हैं?")],
                ),
                turn_complete=True,
            )
            r_audio = 0
            r_text: list[str] = []

            async def wait_resume_reply() -> None:
                nonlocal r_audio
                while True:
                    async for msg in s2.receive():
                        if msg.server_content:
                            sc = msg.server_content
                            if sc.output_transcription and sc.output_transcription.text:
                                r_text.append(sc.output_transcription.text)
                            if sc.model_turn and sc.model_turn.parts:
                                for p in sc.model_turn.parts:
                                    if p.inline_data and p.inline_data.data:
                                        r_audio += len(p.inline_data.data)
                            if sc.turn_complete and r_audio > 0:
                                print(
                                    f"RESUME_REPLY ms={int((time.perf_counter() - t_r) * 1000)} "
                                    f"audio_bytes={r_audio} text={''.join(r_text).strip()}",
                                    flush=True,
                                )
                                return

            await asyncio.wait_for(wait_resume_reply(), timeout=20)


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in services/api/.env")
    asyncio.run(test_live_session(api_key))


if __name__ == "__main__":
    main()
