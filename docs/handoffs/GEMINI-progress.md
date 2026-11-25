# Parampara — Gemini Build Progress

Updated: 2026-11-26 01:16 IST
Worktree: `../pp-gemini`

| Task | Title | Status | Branch / PR | Evidence | Blocked / Needs from Human |
| --- | --- | --- | --- | --- | --- |
| Onboarding | Read all specs & contracts | done | `docs/handoffs/GEMINI-understanding.md` | Full spec + contract review, 8 spec gaps logged | None |
| T-003 | Live API and TTS spike | done (`d91d2da`) | `agent/gemini/T-003-live-spike` | Real API probes (`gemini-3.8-live`, `gemini-3.8-flash-lite-tts`, `gemini-3.5-flash`, `flash-lite`), resumption verified; `make check` green | Remote `git push` / `gh pr create` denied by sandbox policy |
| T-013 | Edge engine pure modules | done (`3db32b2`) | `agent/gemini/T-013-edge-pure` (from T-003) | `colour.ts` (exemplar), `calibrate.ts`, `features.ts`, `rules.ts`; 15/15 Vitest + <12 ms benchmark; `make check` green | Push & open PR |
| T-022 | Compiler deterministic tools | done (`07821e5`) | `agent/gemini/T-022-compiler-tools` (from T-013) | `skill_lint.py`, `keyframes.py` (real ffmpeg), `assemble.py`; `make check` green | Push & open PR |
| T-031 | Verifiable credential tools | done (`e07a4d1`) | `agent/gemini/T-031-vc-tools` (from T-022) | `jcs.py`, `multikey.py`, `vc.py`, 3 shared vectors, CR-002; `make check` green | Push & open PR |
| T-032 | Merkle evidence root | done (`030ba0e`) | `agent/gemini/T-032-merkle` (from T-031) | `merkle.py` + `EVIDENCE_QUERY_SQL`; `make check` green | Push & open PR |
| T-010 | Database migrations, RLS, minimal seed | done (`e034317`) | `agent/gemini/T-010-db-migrations` (from T-032) | `0001_init.sql`, `0002_rls.sql`, `0003_views.sql`, `db/seed/seed.py`; `make check` green | Docker daemon stopped (`DOCKER_RUNNING=no`) |
| T-011 | API skeleton, exemplars, LLM gateway, telemetry | done (local commit) | `agent/gemini/T-011-api-skeleton` (from T-010) | Exemplars (`hashing.py`, `skill_versions.py` repo+route), `llm.py`, `TelemetryBus` SSE, DID doc, `test_no_surveillance.py`; live uvicorn HTTP check OK; 35/35 pytest; `make check` green | Push & open PR |
| T-000 | Accounts, registration, organiser email | blocked (Human) | - | - | Human task |
| T-004 | Record master demo & practice clips | blocked (Human) | - | - | Needs physical terminal-block kit recordings |
| T-026 | Prompt tuning on real clips | blocked (Human) | - | - | Depends on T-004 |
| T-046 | Eval recordings and labels | blocked (Human) | - | - | Depends on T-004 |
| T-052 | Video and submission | blocked (Human) | - | - | Human task |
