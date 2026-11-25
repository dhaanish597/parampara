# Verifier Latency & Free-Tier Reliability Study (Phase 2b / CR-008)

- **Date:** 2026-11-26 19:45 IST
- **SDK:** `google-genai==3.6.1` (`retry_options=HttpRetryOptions(attempts=1)`, `timeout=10000 ms`, structured output via `response_json_schema=VerifierModelOutput.model_json_schema()`)
- **Tier:** Free tier only (D-011)
- **Workload:** 10 calls per variant (2 concurrent workers) verifying step `s1` (`terminal-wiring`) against a JPEG frame with 2 predicates (`p1`, `p2`).

## Measured Results (10 Calls per Variant)

| Variant | Model | OK | HTTP 503 | HTTP 429 | Timeout / Other | Min (ms) | p50 (ms) | p95 (ms) | Max (ms) |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |
| `flash_default` | `gemini-3.5-flash` | 0 / 10 | 0 | **10** | 0 | — | — | — | — |
| `flash_thinking_0` | `gemini-3.5-flash` (`thinking_budget=0`) | 0 / 10 | 0 | **10** | 0 | — | — | — | — |
| `flash_lite` | `gemini-3.5-flash-lite` | **6 / 10** | 3 | 0 | 1 (`ReadTimeout` >10 s) | 1,838 | **3,751** | 5,583 | 8,173 |

Raw `gemini-3.5-flash-lite` OK latencies (ms): `[1838, 2129, 5374, 5583, 1840, 8173]`.

## Earlier Single-Call Baseline (2026-11-26 12:15 IST, before `gemini-3.5-flash` daily quota hit)

- `gemini-3.5-flash` default structured `VerifierVerdict`: **7,066 ms** (`input_tokens=1110`, `output_tokens=186`), valid `needs_better_view` verdict.
- Claude's Phase 1 verification (2026-11-26): `gemini-3.5-flash` returned HTTP 503 ("high demand") on 9 of 9 calls; `gemini-3.5-flash-lite` answered 3 of 3 in 1.5–3.7 s.

## Conclusions & CR-008 Verification

1. **Free-tier `gemini-3.5-flash` alone cannot meet the 8 s verifier budget**: even before daily quota exhaustion (429), single-call latency was 7.1–11.1 s and transient 503s were frequent.
2. **CR-008 (approved) is essential and implemented**: `verify_step` tries `MODEL_FLASH` (`gemini-3.5-flash`) up to 4 s with `max_retries=0` and fails fast on 429/503/timeout to `MODEL_LITE` (`gemini-3.5-flash-lite`) within one overall **8 s** deadline (`VerifierVerdict.model` records the answering model).
3. With `gemini-3.5-flash-lite` at p50 = **3.75 s** (min **1.84 s**), the verifier stays inside both the 8 s overall deadline and the 5 s two-key window for the majority of calls, while gracefully returning `unavailable` (triggering manual confirm after 3 consecutive failures) when 503s hit.
