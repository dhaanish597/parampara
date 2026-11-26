# TASKS.md: the Parampara task board

Edited only on `main` by the human or Claude Code. Agents report progress in `docs/handoffs/T-xxx.md` and in their PRs, never here.
Statuses: `todo`, `ready`, `in_progress`, `in_review`, `changes`, `blocked`, `done`, `cut`. Task details and acceptance criteria are in `docs/BUILD_PLAN.md` section 32.
Lanes from 26 November (D-012): Gemini builds the backend, data and evals; Claude builds the web app, deploys, reviews and merges. Batch 1 review: `docs/audits/2026-11-26-gemini-batch-1-review.md`.

| ID | Task | Owner | Reviewer | Depends on | Day | Status | PR |
| --- | --- | --- | --- | --- | --- | --- | --- |
| T-000 | Accounts, registration, organiser email | Human | - | none | Day 0 (25 November) | todo |  |
| T-001 | Repository scaffold | Claude | Codex | T-000 | Day 0 (25 November) | done |  |
| T-002 | Contracts v1 and codegen | Claude | Gemini | T-001 | Day 0 (25 November) | done |  |
| T-003 | Live API and TTS spike | Gemini | Claude | T-000 | Day 0 (25 November) | changes |  |
| T-004 | Record the master demo and practice clips | Human | - | kit delivered | Day 0 (25 November) | todo |  |
| T-010 | Database migrations, RLS, minimal seed | Gemini | Claude | T-002 | Day 1 (26 November) | changes |  |
| T-011 | API skeleton, exemplars, LLM gateway, telemetry | Gemini | Claude | T-002, T-010 | Day 1 (26 November) | changes |  |
| T-012 | Web skeleton, design system, auth | Claude | Gemini | T-002 | Day 1 (26 November) | in_review | https://github.com/dhaanish597/parampara/pull/1 |
| T-013 | Edge engine pure modules | Gemini | Claude | T-002 | Day 1 (26 November) | changes |  |
| T-014 | Edge engine browser modules and calibration UI | Claude | Gemini | T-012, T-013 | Day 1 (26 November) | todo |  |
| T-015 | Live client, coach state machine, coach page | Claude | Gemini | T-003, T-014, T-016 | Day 1 (26 November) | todo |  |
| T-016 | Session endpoints and system instruction builder | Gemini | Claude | T-003, T-011 | Day 1 (26 November) | changes |  |
| T-017 | Deploy skeleton and CI | Claude | Gemini | T-001 | Day 0 to 1 (25 to 26 November) | todo |  |
| T-020 | Verifier and two-key logic | Gemini (API, two-key); Claude (evidence UI) | Claude | T-011, T-015 | Day 2 (27 November) | changes |  |
| T-021 | Skill Compiler graph | Gemini | Claude | T-011, T-022, T-023 | Day 2 (27 November) | todo |  |
| T-022 | Compiler deterministic tools | Gemini | Claude | T-002 | Day 2 (27 November) | changes |  |
| T-023 | Clip pipeline and job worker | Gemini | Claude | T-010, T-011 | Day 2 (27 November) | todo |  |
| T-024 | Capture and Review pages | Claude | Gemini | T-021, T-025 | Day 2 (27 November) | todo |  |
| T-025 | Face blur and canvas recorder | Claude | Gemini | T-014 | Day 2 (27 November) | todo |  |
| T-026 | Prompt tuning on real clips | Gemini | Claude | T-021, T-004 | Day 2 (27 November) | todo |  |
| T-027 | TTS tool and hazard audio job | Gemini | Claude | T-003, T-023 | Day 2 (27 November) | todo |  |
| T-028 | Tacit interviewer | Gemini (API); Claude (interview UI) | Claude | T-015, T-021 | Day 2 (27 November) | todo |  |
| T-030 | Mastery, mode selection, session summary | Gemini | Claude | T-016, T-020 | Day 3 (28 November) | changes |  |
| T-031 | Verifiable credential tools | Gemini | Claude | T-002 | Day 3 (28 November) | changes |  |
| T-032 | Merkle evidence root | Gemini | Claude | T-002 | Day 3 (28 November) | changes |  |
| T-033 | Credential issuance and verify page | Gemini (issuance API, verify.ts); Claude (pages) | Claude | T-030, T-031, T-032 | Day 3 (28 November) | todo |  |
| T-034 | Consent ledger and scopes | Gemini | Claude | T-010, T-011 | Day 3 (28 November) | changes |  |
| T-035 | Consent wallet UI | Claude | Gemini | T-034, T-027, T-036 | Day 3 (28 November) | todo |  |
| T-036 | Hindi copy and consent notice | Gemini | Claude | T-012 | Day 3 (28 November) | todo |  |
| T-037 | Session summary and replay page | Claude | Gemini | T-030 | Day 3 (28 November) | todo |  |
| T-040 | Refinery deterministic pipeline | Gemini | Claude | T-023, T-034 | Day 4 (29 November) | todo |  |
| T-041 | Refinery agent, dataset endpoints, episode viewer | Gemini (agent, endpoints); Claude (viewer) | Claude | T-040 | Day 4 (29 November) | todo |  |
| T-042 | Royalties, payouts, licences, earnings | Gemini | Claude | T-034, T-040 | Day 4 (29 November) | changes |  |
| T-043 | Lab data room and earnings tab | Claude | Gemini | T-041, T-042 | Day 4 (29 November) | todo |  |
| T-044 | Dashboard views and endpoint | Gemini | Claude | T-030, T-033 | Day 4 (29 November) | todo |  |
| T-045 | Dashboard UI | Claude | Gemini | T-044 | Day 4 (29 November) | todo |  |
| T-046 | Eval recordings and labels | Human with Gemini | Claude | T-004 | Day 4 (29 November) | todo |  |
| T-047 | Eval harness and usage report | Gemini | Claude | T-020, T-046 | Day 4 (29 November) | todo |  |
| T-048 | Full seed | Gemini | Claude | T-030 to T-042 | Day 4 (29 November) | todo |  |
| T-049 | Production deploy and phone smoke | Claude | Gemini | all Day 4 tasks | Day 4 (29 November) | todo |  |
| T-050 | Submission audit | Gemini | Claude | M4 | Day 5 (30 November) | todo |  |
| T-051 | Fix pass, unification pass, documentation | Claude | Codex | T-050 | Day 5 (30 November) | todo |  |
| T-052 | Video and submission | Human | - | T-051 | Day 5 (30 November) | todo |  |
| T-053 | Tag and freeze | Claude | - | T-052 | Day 5 (30 November) | todo |  |

## Milestones

| Milestone | Due (IST) | Check | Status |
| --- | --- | --- | --- |
| M1 The coach talks | 26 Nov 23:30 | Phone over HTTPS, fixture graph, Hindi coaching through 6 steps, Ruko on phase into N | todo |
| M2 Master teaches, verifier judges | 27 Nov 23:30 | Master clip compiled, reviewed, interviewed, approved as v2; no step completes without both keys | todo |
| M3 Trust | 28 Nov 23:30 | Credential verifies by QR on another phone and fails tamper test; consent ledger entry verified | todo |
| M4 Whole loop in production | 29 Nov 23:30 | Smoke test 34.2 passes on Android and iPhone over mobile data | todo |
| Submission | 30 Nov 12:00 | Checklist 34.3 complete, tag v1.0-submission | todo |
