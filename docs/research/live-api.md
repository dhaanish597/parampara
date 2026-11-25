# Gemini Live API Research & Free-Tier Verification (T-003)

**Checked:** 2026-11-26 IST
**SDKs verified:** `google-genai==3.6.1` (Python 3.12.16), `@google/genai@1.30.0` (browser ESM)
**Official docs:**
- [Gemini 3.8 Live](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-live)
- [Live API overview](https://ai.google.dev/gemini-api/docs/live-api)
- [Ephemeral tokens in Live API](https://ai.google.dev/gemini-api/docs/ephemeral-tokens)
- [Session management with Live API](https://ai.google.dev/gemini-api/docs/live-session)
- [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits)

## 1. Verified Model IDs & Capabilities

| Env Var | Verified Model ID | Status | Verified Behavior (2026-11-26) |
| --- | --- | --- | --- |
| `MODEL_LIVE` | `gemini-3.8-live` | GA (Sep 2026) | Bidi WebSocket audio+image+tools, 131,072 input / 65,536 output tokens |
| `MODEL_FLASH` | `gemini-3.5-flash` | GA | Structured JSON output OK (`latency_ms=3466`) |
| `MODEL_LITE` | `gemini-3.5-flash-lite` | GA | Structured JSON output OK (`latency_ms=2030`) |
| `MODEL_TTS` | `gemini-3.8-flash-lite-tts` | GA (Sep 2026) | `v1beta` audio/wav output OK (`latency_ms=2783`, see `docs/research/tts.md`) |

### Important `gemini-3.8-live` API Rules (Migration Notes)
- **Omit `thinking_config` / `thinking_level`**: `gemini-3.8-live` has built-in interleaved reasoning and rejects `thinking_level`.
- **Omit `proactive_audio: false`**: Proactive audio is permanently enabled; setting it to `false` returns an error.
- **Omit `enable_affective_dialog`**: Removed from the API.
- **Response modality**: Only `["AUDIO"]` is supported; enable `output_audio_transcription={}` for Hindi captions.
- **Asynchronous function calling**: `NON_BLOCKING` is the default; scheduling supports `SILENT`, `WHEN_IDLE`, and `INTERRUPTED`.
- **Client content updates**: `send_client_content(..., turn_complete=True)` is supported throughout the session lifecycle and unconditionally interrupts active model generation.
- **Turn coverage**: Defaults to `TURN_INCLUDES_AUDIO_ACTIVITY_AND_ALL_VIDEO`; only send video frames (<= 1 fps) during active coaching (`COACHING` state) to stay inside context and free-tier budgets.

## 2. Ephemeral Token Minting (`v1alpha`)

- **API version required:** `http_options={"api_version": "v1alpha"}` on both the minting client (server) and the connecting client (browser).
- **Python SDK call verified:**
  ```python
  token_client = genai.Client(api_key=api_key, http_options={"api_version": "v1alpha"})
  token = token_client.auth_tokens.create(
      config=types.CreateAuthTokenConfig(
          uses=1,
          expire_time=now + datetime.timedelta(minutes=30),
          new_session_expire_time=now + datetime.timedelta(minutes=1),
          live_connect_constraints=types.LiveConnectConstraints(
              model="gemini-3.8-live",
              config=live_config,
          ),
      )
  )
  # token.name starts with "auth_tokens/..."
  ```
- **API key format:** Project key starts with `AQ.` (Google AI Studio / Gemini key format) and works transparently via `genai.Client(api_key=...)` (`x-goog-api-key` header).
- **Important note on resumption with ephemeral tokens:** Because `uses=1` locks a token to one connection, reconnecting with a `sessionResumption` handle after a `GoAway` or socket drop requires minting a fresh single-use ephemeral token from the backend (passing the saved `handle` into `live_connect_constraints.config.session_resumption.handle`) rather than reusing the consumed token.

## 3. Session Lifetime, Compression & Resumption

- **Without compression:** audio+video sessions terminate at ~2 minutes; audio-only sessions terminate at ~15 minutes. Single WebSocket connections reset at ~10 minutes.
- **Verified config for 6+ minute video sessions:**
  ```json
  {
    "contextWindowCompression": {
      "triggerTokens": 32000,
      "slidingWindow": { "targetTokens": 16000 }
    },
    "sessionResumption": { "handle": null }
  }
  ```
- **Token math at 1 fps:** ~258 tok/s video + ~25 tok/s audio ≈ 283 tok/s (~17,000 tok/min). With `triggerTokens: 32000` and `targetTokens: 16000`, sliding-window compression triggers before the 2-minute wall and keeps a 6-minute session well inside the 131,072-token window.
- **Resumption verified empirically (`spikes/live/probe_live.py`):**
  - Initial connection returned `session_resumption_update` (`handle_len=36`, `resumable=True`).
  - Reconnecting on a brand-new WebSocket with `handle` took `908 ms` and retained full tool-call state (`हम अभी 'तार और फेरूल जाँचें' वाले कदम पर हैं।`).
- **`GoAway` handling:** Listen for `msg.go_away` (`time_left`), request a fresh resumption token from the API, and reconnect seamlessly before close.

## 4. Audio Formats & Recommended Hindi Voice

- **Input audio:** Raw 16-bit PCM, 16 kHz, mono, little-endian (`audio/pcm;rate=16000`), streamed every ~100 ms.
- **Output audio:** Raw 16-bit PCM, 24 kHz, mono, little-endian (`audio/pcm;rate=24000`).
- **Input video:** JPEG `768x768` at <= 1 fps (only during `COACHING`).
- **Recommended Hindi voice:** **`Orus`** — warm, calm, senior-trainer male timbre suited for the "Ustaad" persona; clean Devanagari pronunciation verified on both Live API and TTS (`Kore` is a clean female alternative if needed).

## 5. Measured Latencies (2026-11-26, Free-Tier Key)

| Operation | Measured Latency | Notes |
| --- | --- | --- |
| Ephemeral token mint (`v1alpha`) | 447 ms (507 ms cold) | `auth_tokens.create`, `uses=1` |
| Live WebSocket connect (ephemeral token) | 1,705 ms | Includes TLS + setup handshake |
| First tool call (`get_current_step`) | 306 ms | After text+image turn |
| First audio byte after tool response | 403 ms | `audio/pcm` 24 kHz |
| Full Hindi greeting turn | 3,561 ms | 136,322 bytes PCM (~2.8 s speech); `"नमस्ते, चलिए आज का काम शुरू करते हैं।"` |
| Session resumption reconnect | 908 ms | Preserved step `s1` state |
| Resumed Hindi reply | 3,649 ms | 155,040 bytes PCM; `"हम अभी 'तार और फेरूल जाँचें' वाले कदम पर हैं।"` |

## 6. Free-Tier Quota Assessment (Decision D-011)

Per [Gemini API rate limits](https://ai.google.dev/gemini-api/docs/rate-limits) and Google AI Studio free-tier behaviour:
- All 4 required model families (`gemini-3.8-live`, `gemini-3.5-flash`, `gemini-3.5-flash-lite`, `gemini-3.8-flash-lite-tts`) are **available on the free tier** (`Free of charge` input/output) and passed live probes on our project key on 2026-11-26.
- **Quota constraints to design around on free tier:**
  1. **RPM / RPD caps on Flash & Flash-Lite:** Free-tier `generateContent` projects are subject to tight per-minute (typically 5–15 RPM) and daily (typically 20–250 RPD depending on model) caps.
     - **Impact on Skill Compiler (`detail` node, BUILD_PLAN 14.2):** Parallel LangGraph `Send` fan-out of 6 simultaneous `gemini-3.5-flash` calls risks triggering 429s on free tier. **Mitigation:** bound concurrency (semaphore of 2) with jittered backoff in `agents/llm.py` (13.1), and keep `MODEL_LITE` for SOP/refinery tasks.
     - **Impact on Eval Harness (BUILD_PLAN 29.2):** Replaying 30 runs × 6 steps = 180 `gemini-3.5-flash` verifier calls may hit daily free-tier RPD in a single burst. **Mitigation:** run evals in small batches, pace requests, and cache verified frames by SHA-256 during development.
  2. **Live API concurrent sessions:** Free tier allows limited concurrent Live sessions (typically 1–3). Keep one active session at a time during demos and always close sockets cleanly on stop/unmount.
  3. **Scripted fallback & cached TTS:** Pre-generate and cache hazard WAV clips once per skill version (`tts_hazards` job), and keep `SCRIPTED_FALLBACK` (16.7) functional so demos never stall if a free-tier 429 occurs.
  4. **Local macOS TLS note:** In sandboxed macOS environments where `truststore` cannot access Keychain (`OSStatus -26276`), set `SSL_CERT_FILE=$(python -c "import certifi; print(certifi.where())")`.

## Free-Tier 429 & 503 Quota Log (D-011)

| Timestamp (IST) | Model | Status | Context |
| :--- | :--- | :---: | :--- |
| 2026-11-26 19:45 | `gemini-3.5-flash` (default) | 429 (10/10) | Phase 2b 10-call verifier latency benchmark |
| 2026-11-26 19:45 | `gemini-3.5-flash` (`thinking_budget=0`) | 429 (10/10) | Phase 2b 10-call verifier latency benchmark |
| 2026-11-26 19:45 | `gemini-3.5-flash-lite` | 503 (3/10), 0x 429 | Phase 2b 10-call verifier latency benchmark (6/10 OK, p50 3,751 ms) |
