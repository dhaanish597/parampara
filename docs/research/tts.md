# Gemini TTS Research & Sample Verification (T-003)

**Checked:** 2026-11-26 IST
**Official docs:**
- [Gemini 3.8 Flash TTS](https://ai.google.dev/gemini-api/docs/models/gemini-3.8-flash-tts)
- [Text-to-speech generation (TTS)](https://ai.google.dev/gemini-api/docs/speech-generation)

## 1. Selected Model & Voice

- **`MODEL_TTS`:** `gemini-3.8-flash-lite-tts`
- **Voice:** `Orus` (matches the Live Coach "Ustaad" voice so local pre-error "Ruko!" interrupts blend seamlessly with the live coach)
- **API Version:** **`v1beta` required** (`genai.Client(api_key=..., http_options={"api_version": "v1beta"})`). The SDK defaults to `v1`, which does not expose Gemini 3.8 TTS features.

### Why `gemini-3.8-flash-lite-tts` over `gemini-3.8-flash-tts`
Both models share the exact same API schema, support Hindi natively, and are available on the free tier:

| Model | Measured Latency (Hindi hazard clip) | Output Size | Format | Recommendation |
| --- | --- | --- | --- | --- |
| `gemini-3.8-flash-lite-tts` | **2,783 ms** | 121,948 bytes (2.38 s) | `audio/wav` (`pcm_s16le`, 24 kHz, mono) | **Selected (`MODEL_TTS`)** — faster, higher free-tier throughput, recommended replacement for `gemini-3.1-flash-tts-preview` |
| `gemini-3.8-flash-tts` | 3,064 ms | 132,028 bytes | `audio/wav` (`pcm_s16le`, 24 kHz, mono) | Available as high-expressiveness upgrade if needed |

## 2. Important Implementation Details

- **Default output is WAV (`audio/wav`) with a standard RIFF header** (`b'RIFF'`), NOT headerless raw PCM. Write the returned `part.inline_data.data` bytes directly to `.wav` (or transcode to `.mp3` with `ffmpeg` if smaller storage is desired). Do **not** wrap in a second WAV header.
- **Strict verbatim transcript:** Gemini 3.8 TTS speaks inline text literally. Do not put stage directions inside the text string; pass only the exact Hindi hazard line (e.g. `"रुको! लाल तार N में नहीं जाता।"`).
- **Fallback:** Per `BUILD_PLAN.md` 14.8, if TTS fails or hits a free-tier quota limit, leave `interrupt_audio_path` empty so the browser falls back to `window.speechSynthesis` with `lang = "hi-IN"`.

## 3. Sample Verification

- Script: `spikes/tts/generate_hindi_sample.py`
- Sample clip: `spikes/tts/ruko_sample.wav`
- Text: `"रुको! लाल तार N में नहीं जाता।"`
- `ffprobe` verification:
  - `format_name=wav`
  - `codec_name=pcm_s16le`
  - `sample_rate=24000`
  - `channels=1`
  - `duration=2.380000`
  - `size=121948`
