# Gemini: finish the application (D-013)

Run from `/Users/dhaanish/Documents/pp-gemini`. Paste the first block once. If a session ends early, paste the short block at the bottom.

## Prompt

```text
You are now the builder for ALL remaining application code in Parampara, backend and web. Claude Code is the lead: it deploys, reviews, merges and pushes. You run one long loop, with sub-agents and test-driven development, until every task in section 4 is done or truly blocked.

## 0. Read first
Run `git fetch origin`, then use `git show origin/main:<path>` if your branch is behind. Read: AGENTS.md, GEMINI.md, docs/DECISIONS.md (D-011, D-012, D-013), docs/CHANGES.md, docs/TASKS.md, docs/handoffs/GEMINI-progress.md, docs/handoffs/T-012.md, and before each task its BUILD_PLAN.md task card (section 32) plus the sections it lists.
D-013 overrides older rules: your lane now includes all of apps/web, and you work through many tasks in one session. Where this prompt and GEMINI.md or the batch 2 prompt differ, this prompt wins. All product and safety rules in AGENTS.md still hold.

## 1. Environment, checked by Claude on 26 November
- Branches agent/gemini/T-003 to T-023 are pushed to GitHub. Tip: agent/gemini/T-023-clip-worker (1832b8a).
- services/api/.env and apps/web/.env.local in this worktree are filled (local Supabase URL and keys, demo org id, MODEL_TTS). The Gemini and Langfuse keys were accepted by the real services; all four model ids are listed for the Gemini key. Never print, copy or commit values.
- Local Supabase runs on Colima (DB 127.0.0.1:54322, API 127.0.0.1:54321). If down: `colima start`, then `supabase start -x studio,imgproxy,vector,logflare,edge-runtime,realtime,mailpit,supavisor`.
- ffmpeg, ffprobe, gitleaks, uv, pnpm and Playwright browsers are installed.
- PAYOUT_PROVIDER=simulated. RazorpayX keys are empty on purpose (D-010). Do not wait for them.
- Do not push. Commit locally; Claude pushes. A denied push is never a blocker.
- If curl to loopback is denied, use a Python httpx script or Playwright.

## 2. First fix: the quality gate hides failures
Your batch 2 report said the gate passed on real Supabase. On T-023, Claude ran `make db-reset && make check` with the filled .env: 4 tests fail, 74 pass, 1 skips.
- tests/test_api_skeleton.py::test_p0_1_ignores_jwt_roles_and_persists_anon_demo_join_in_db (401, expected 200)
- tests/test_consent_ledger.py::test_consent_api_enforces_owner_and_validations (ForeignKeyViolation: consent_records.subject_user_id not in profiles)
- tests/test_sessions.py::test_client_completed_and_vlm_key_rejected_and_complete_idempotent (starts a session, same area as the next one)
- tests/test_sessions.py::test_two_key_within_5s_clean_run_and_aborted_not_a_run (ForeignKeyViolation: clips.owner_user_id not in profiles)
With DATABASE_URL and the SUPABASE_ variables blank the same suite shows 71 passed and 8 skipped and `make check` goes green, so a green gate has been possible without exercising the database.
Required:
1. Find each root cause. Product bugs come first: a signed-in user without a profile must get a clear ApiError (or get a profile through the correct path), never a 500.
2. Tests set their own configuration and never depend on what is in .env. Database tests create real auth users and profiles.
3. With local Supabase up, `make check` runs the database tests with no skips except RUN_LIVE ones. Put the pass and skip counts in every handoff.
4. Fix in the commit that introduced each bug (fixup, then `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash --update-refs main`), then run `make check` on every branch of the stack.

## 3. Method for every task
1. Plan: restate the acceptance criteria, list files and tests, name the exemplar (BUILD_PLAN 31.4).
2. Sub-agents: one summarises the spec, one writes failing tests, one implements, one fresh-context reviewer applies 31.7. No two edit the same file. You integrate.
3. Red, green, refactor. Files at most 300 lines, functions at most 40, no dead code, user-facing strings in hi.json and en.json, model ids only in the two config files.
4. Verify for real. API: real local Supabase, real HTTP calls, check rows and logs. AI: one real free-tier call per changed path. Web: `pnpm --filter @parampara/web gen:api`, build, then drive the page in Playwright against the running API at 390x844, in Hindi and English, with a fake camera where needed; save screenshots to docs/evidence/T-xxx/ and look at them before claiming anything. No mocked API in this check.
5. `make check` green, handoff written. An AC is "met" only if you observed it; otherwise "partly" or "not met", with the reason.
6. One branch per task, stacked on your tip: agent/gemini/T-xxx-<slug>.

## 4. Order (critical path first; finish one before the next)
A. The section 2 fix.
B. Coach talks (M1): T-014, T-015, then the T-020 evidence UI.
C. Trust: T-033 (issuance API, verify.ts, verify page with QR and tamper test), T-037.
D. Master teaches (M2): T-027, T-021, T-025, T-024, T-028.
E. Consent: T-036, T-035.
F. Data and money: T-040, T-041, remaining T-042 gaps, T-043.
G. Numbers: T-044, T-045, T-047, T-048.
H. Add `make dev` (web, API, worker) as soon as B needs it, and `make test-e2e` covering the BUILD_PLAN 34.2 smoke steps locally.
I. T-050: audit the whole repo against the plan (31.11) into docs/audits/, then fix your own findings.
After each of B to G, run in a browser the 34.2 smoke steps built so far, end to end, and fix breakage before moving on.
Time: submission is 30 November 12:00 IST. Targets: A to C by 27 November night, D and E by 28 November night, F and G by 29 November night. If behind, cut in the order of BUILD_PLAN 33.3, say so in the progress file, and never cut anything on its never-cut list.

## 5. Not yours
Dockerfile, .github/, Render, Vercel, cloud Supabase, production env, T-017, T-049, T-051, T-053, merges, pushes, docs/BUILD_PLAN.md, docs/TASKS.md, docs/DECISIONS.md. Never disable a check or lower a threshold.

## 6. Nothing waits
- Missing master or eval recordings (T-004, T-046): generate your own clearly labelled test media, build the whole path so real clips drop in with no code change, and mark that AC "partly". Never present generated results as real; EVAL_REPORT.md says which inputs were generated.
- Contract or plan gap: write a CR in docs/CHANGES.md. If the change is additive (new optional field, new endpoint), implement it in its own commit, regenerate with `make contracts`, mark it "pending Claude" and continue. If it changes or removes behaviour, build the part that does not depend on it and continue.
- Free-tier 429: back off, reuse results cached by input SHA-256, log it in docs/research/live-api.md, switch to work that needs no model and retry later. Never use another key or project.
- Anything only the human can do (install, secret, login, phone test): add a row under "NEEDS FROM HUMAN" at the top of GEMINI-progress.md with the exact command or where to get it, then carry on with other work.
- The same item failing three times: record the evidence, move on, return to it at the end.
Stop only when no item in section 4 can advance.

## 7. Reporting
Keep docs/handoffs/GEMINI-progress.md current: NEEDS FROM HUMAN, then for each task the status, branch, commit, test counts, evidence and API changes. At the end of each group B to G write "READY FOR CLAUDE REVIEW: group <letter>" and continue without waiting. If Claude merges to main, run `git fetch origin && git rebase --update-refs origin/main` from your tip.
```

## Continue (new or interrupted session)

```text
Continue the loop in docs/GEMINI_FINISH.md (`git fetch origin && git show origin/main:docs/GEMINI_FINISH.md`). Read docs/handoffs/GEMINI-progress.md, check the last claimed item for real (`make db-reset && make check`, note pass and skip counts), then carry on with the next unfinished item in section 4 order.
```
