"""Minimal HTTPS-ready FastAPI server for T-003 Live API phone spike.

Run (with self-signed cert or behind Cloudflare Tunnel / ngrok for phone HTTPS):
    cd services/api && uv run uvicorn spikes.live.server:app --app-dir ../.. --host 0.0.0.0 --port 8443
"""

from __future__ import annotations

import datetime
import os
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "services" / "api" / ".env")

LIVE_MODEL = os.environ.get("MODEL_LIVE", "gemini-3.8-live")
VOICE_NAME = "Orus"
INDEX_HTML = Path(__file__).resolve().parent / "index.html"

app = FastAPI(title="Parampara T-003 Live Spike")


@app.get("/", response_class=HTMLResponse)
async def index() -> str:
    return INDEX_HTML.read_text(encoding="utf-8")


@app.post("/token")
async def mint_token() -> dict[str, object]:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="GEMINI_API_KEY not configured")

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(minutes=30)
    tool = types.Tool(
        function_declarations=[
            types.FunctionDeclaration(
                name="get_current_step",
                description="Returns the active training step and coaching mode.",
                parameters=types.Schema(type=types.Type.OBJECT, properties={}),
            )
        ]
    )
    live_config = types.LiveConnectConfig(
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
        session_resumption=types.SessionResumptionConfig(handle=None),
        speech_config=types.SpeechConfig(
            voice_config=types.VoiceConfig(
                prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=VOICE_NAME)
            )
        ),
    )

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
    token = client.auth_tokens.create(
        config=types.CreateAuthTokenConfig(
            uses=1,
            expire_time=expires_at,
            new_session_expire_time=now + datetime.timedelta(minutes=1),
            live_connect_constraints=types.LiveConnectConstraints(
                model=LIVE_MODEL,
                config=live_config,
            ),
        )
    )
    return {
        "ephemeral_token": token.name,
        "model": LIVE_MODEL,
        "voice": VOICE_NAME,
        "expires_at": expires_at.isoformat().replace("+00:00", "Z"),
    }
