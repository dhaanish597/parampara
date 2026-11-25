# Gemini: first session

Claude Code bootstrapped the repo on 25 Nov. Done: T-001 scaffold, T-002 contracts (read `docs/handoffs/T-001.md` and `T-002.md`).

## Your first task: T-003 Live API and TTS spike

1. Read `AGENTS.md`, `GEMINI.md`, then `docs/BUILD_PLAN.md` sections 8.1, 14.8, 16.1 to 16.6, and the T-003 card in section 32.
2. Work in `../pp-gemini` on branch `agent/gemini/T-003-live-spike` (already created by Claude).
3. Secrets: `services/api/.env` holds `GEMINI_API_KEY` (git-ignored; never print it or commit it). Spikes load it from that file.
4. Deliverables: `spikes/live/`, `spikes/tts/`, `docs/research/live-api.md`, `docs/research/tts.md`, `docs/research/versions.md`, `docs/handoffs/T-003.md`.
5. The model ids in BUILD_PLAN 8.1 are defaults; verify them against the current official docs and record what really works.
6. `make check` must pass. Open a PR titled `T-003: Live API and TTS spike`.

Bootstrap prompt (Antigravity): see the end of `GEMINI.md`.

## Head start (checked by Claude on 25 Nov with the project key, models list endpoint)

- Present on the key: `gemini-3.8-live`, `gemini-3.8-live-extended-thinking`, `gemini-3.1-flash-live-preview` (all `bidiGenerateContent`), `gemini-3.5-flash`, `gemini-3.5-flash-lite`.
- TTS candidates: `gemini-3.8-flash-tts`, `gemini-3.8-flash-lite-tts`, `gemini-3.1-flash-tts-preview`. Pick one for `MODEL_TTS` and record why.
- **Decision (human, 26 Nov): free tier only. Billing will not be enabled.** Design every spike around free-tier rate and session limits. Record the measured limits (requests per minute, concurrent Live sessions, daily caps) in `docs/research/live-api.md`, and say clearly in the handoff if a plan assumption (6-minute video session, 1 fps frames, 4 model families) does not fit. Do not work around quotas with other keys or projects.
- The key format starts with `AQ.`, not `AIza`. Send it as the `x-goog-api-key` header or through the SDK.

## Hands-off mode

Batch 1 used `docs/GEMINI_PROMPT.md`. From 26 November use `docs/GEMINI_NEXT.md` (verify, fix the review findings, then build the backend lane until blocked).
