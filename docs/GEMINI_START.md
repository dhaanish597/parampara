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
