"""T-003 TTS spike: verify Gemini 3.8 TTS models on v1beta and generate Hindi hazard sample."""

from __future__ import annotations

import os
import time
from pathlib import Path

from dotenv import load_dotenv
from google import genai
from google.genai import types

ROOT = Path(__file__).resolve().parents[2]
load_dotenv(ROOT / "services" / "api" / ".env")

SAMPLE_TEXT = "रुको! लाल तार N में नहीं जाता।"
MODELS = ["gemini-3.8-flash-lite-tts", "gemini-3.8-flash-tts"]
VOICE_NAME = "Orus"
OUT_PATH = Path(__file__).resolve().parent / "ruko_sample.wav"


def run_tts(client: genai.Client, model: str, voice: str) -> tuple[bytes, str, int]:
    t0 = time.perf_counter()
    resp = client.models.generate_content(
        model=model,
        contents=SAMPLE_TEXT,
        config=types.GenerateContentConfig(
            response_modalities=["AUDIO"],
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(voice_name=voice)
                )
            ),
        ),
    )
    latency_ms = int((time.perf_counter() - t0) * 1000)
    cand = resp.candidates[0] if resp.candidates else None
    parts = cand.content.parts if cand and cand.content and cand.content.parts else []
    for part in parts:
        if part.inline_data and part.inline_data.data:
            mime = part.inline_data.mime_type or "unknown"
            return part.inline_data.data, mime, latency_ms
    raise RuntimeError(f"No audio inline_data returned for {model}")


def main() -> None:
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise SystemExit("GEMINI_API_KEY missing in services/api/.env")

    client = genai.Client(api_key=api_key, http_options={"api_version": "v1beta"})
    saved = False
    for model in MODELS:
        try:
            audio_bytes, mime, latency_ms = run_tts(client, model, VOICE_NAME)
            header = audio_bytes[:4]
            print(
                f"OK model={model} voice={VOICE_NAME} latency_ms={latency_ms} "
                f"bytes={len(audio_bytes)} mime={mime} magic={header!r}"
            )
            if not saved:
                OUT_PATH.write_bytes(audio_bytes)
                saved = True
        except Exception as exc:
            print(f"ERR model={model}: {type(exc).__name__}: {exc}")


if __name__ == "__main__":
    main()
