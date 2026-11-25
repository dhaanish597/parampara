# Gemini: batch 2 hands-off prompt (verify, fix, then build the backend until blocked)

Before pasting: start Docker Desktop (the Supabase CLI 3.4.0 is installed). Run Gemini from `/Users/dhaanish/Documents/pp-gemini`. Paste the block once; it loops until no unblocked task is left.

```text
You are the backend builder for Parampara, working in the pp-gemini worktree. Claude Code is the lead: it builds the web app in parallel, reviews your branches and merges them. You run a long autonomous loop, using sub-agents and test-driven development, until you reach a blocker you cannot route around. Then you write it down and stop.

## 0. Read first (all of it, before any code)
On main (use `git show main:<path>` if your branch is behind): AGENTS.md, GEMINI.md, docs/audits/2026-11-26-gemini-batch-1-review.md, docs/DECISIONS.md (especially D-011 free tier and D-012 lanes), docs/CHANGES.md (CR-001 to CR-007), docs/TASKS.md, and every docs/BUILD_PLAN.md section named by a task or finding you work on. Then rebase your stack on main: `git fetch origin && git rebase --update-refs main` from the tip branch (agent/gemini/T-020-verifier-two-key).

Why batch 1 was sent back: the tests passed while the product did not work. The verifier test mocked Gemini, so a 400 on every real call went unseen. The migration test checked strings, so RLS holes went unseen. The session test trusted client events, so a fake clean run went unseen. Rule from now on: a task or fix is done only when you have run the real thing and observed it.

## 1. Your lane (D-012). Never edit outside it
Yours: services/, db/, supabase/ (new), evals/, docs/research/, docs/handoffs/, docs/legal/, the pure TS modules apps/web/lib/edge/{colour,calibrate,features,rules}.ts, apps/web/lib/coach/twoKey.ts, apps/web/lib/vc/verify.ts and their tests, and the Makefile targets db-reset, eval, usage.
Claude's: everything else in apps/web (app/, components/, lib/live, lib/coach/machine.ts, lib/edge browser modules, lib/i18n), packages/, contracts/, CI and deploy, docs/BUILD_PLAN.md, docs/TASKS.md, docs/DECISIONS.md.
If you need something in Claude's lane (a contract field, a plan change, a web hook), write a CR in docs/CHANGES.md on your branch, mark it in your handoff, and continue with something else.
API rule so Claude can generate the web client: every route declares a Pydantic response model (from domain/generated.py where a contract exists), every error is ApiError (including validation errors and unhandled exceptions), and the OpenAPI document stays stable. When you add or change a route, list it in your handoff under "API changes".

## 2. Method for every task and every fix: sub-agent-driven TDD
1. PLAN: restate the acceptance criteria or the finding, list files and tests, name the exemplar (BUILD_PLAN 31.4).
2. DELEGATE: one sub-agent summarises the spec sections and prior handoffs, one writes failing tests from the AC, one implements, one fresh-context reviewer checks the diff against BUILD_PLAN 31.7. Give each a complete brief. Never let two sub-agents edit the same file. You integrate and decide.
3. RED: run the new tests and confirm they fail for the right reason. GREEN: minimum code to pass. REFACTOR: exemplar style, files under 300 lines, functions under 40, no dead code, no TODO without a task id, model ids only in settings.py.
4. VERIFY FOR REAL (not optional):
   - Database: run against real local Supabase (`supabase start`, `make db-reset`). For RLS, query as anon and as authenticated users with real JWTs from local Supabase auth.
   - API: run uvicorn against that database, call the endpoints with curl, check the response bodies, the logs and the rows written.
   - AI: one real free-tier Gemini call per changed AI path. Record latency, tokens and any error text.
   - Paste the commands and what came back into the handoff.
5. `make check` green on every branch of your stack.
6. Handoff: an AC is "met" only if you observed it. Otherwise "partly" or "not met", with the reason.

## 3. Phase 0: baseline. Prove the current state before changing anything
Write docs/handoffs/GEMINI-batch2-baseline.md before any fix.
1. `make check` on the tip. Record the result.
2. `supabase init` if needed. Wire `make db-reset` to apply db/migrations/*.sql in order (pgvector on) and run db/seed/seed.py, through supabase/config.toml or a script. Run it twice.
3. Reproduce every P0 in the review against the running API and database, with the real command and output: forged unsigned JWT accepted by /v1/me; Live token without tools (real Live session, no get_current_step call); verifier 400 on a real call; six client "completed" events giving clean_run true, and repeated /complete raising mastery; anon reading v_earnings; truncate consent_records as authenticated; user B granting consent on user A's clip; zero-byte default issuer seed.
4. If something does not reproduce, say so with evidence. If you find something the review missed, add it.

## 4. Phase 1: fix P0-1 to P0-8, one at a time, test first
For each: a failing test that reproduces the observed failure, the fix, the test passing, and the Phase 0 reproduction re-run showing it is gone.
Commit each fix as `git commit --fixup=<commit of the task that introduced the code>` on the tip branch, then restack with `GIT_SEQUENCE_EDITOR=: git rebase -i --autosquash --update-refs main`. After every restack: `for b in $(git for-each-ref --format='%(refname:short)' refs/heads/agent/gemini/); do git switch -q $b && make check >/dev/null || echo FAIL $b; done; git switch -q agent/gemini/T-020-verifier-two-key`.
- P0-1 auth: verify Supabase JWTs against the JWKS (local Supabase while developing); profile and memberships come from the database; demo join inserts memberships for an anonymous Supabase user. No `demo:` tokens outside tests.
- P0-2 Live token: one function builds the 16.3 config and the token's LiveConnectConfig is built from it, tools included. Test that they are equal. A real Live run must show a get_current_step call.
- P0-3 gateway: `response_json_schema=Model.model_json_schema()`; the exception message goes into the error trace and model_calls.error. Add a pytest marker `live` (runs only with RUN_LIVE=1) with one real call per structured agent.
- P0-4 server-side two-key: two_key only from a stored vlm_key written by /verify plus an edge_key within 5 s; /complete idempotent; aborted sessions are not runs.
- P0-5 to P0-8 as the review says.

## 5. Phase 2: the P1 items in the review
Order: persistence (db/pool.py; repos for sessions, step_events, calibration, mastery, consents with the 21.2 FOR UPDATE append, model_calls, trace_events; the trace bus mirrors to Postgres; Langfuse spans when keys are set); verifier (store the frame in the frames bucket, load the reference keyframe, one 8 s overall deadline, deterministic predicate coverage check; measure 10 real calls with the lowest thinking setting and with gemini-3.5-flash-lite, write docs/research/verifier-latency.md, and raise a CR if 8 s cannot hold); API contract fixes; licences and earnings routes (23.1, idempotent, one transaction); credentials (proof metadata checks, negative vectors, evidence query of counted runs only); consent route validation and idempotency; edge engine and twoKey items 1 to 8; database items; T-003 gaps (resume with a fresh ephemeral token, measured free-tier limits). Install @vitest/coverage-v8 and report real coverage.
CR-003 to CR-007: implement only those whose Decision line on main says approved. Re-check CHANGES.md on main at the start of every task.
When Phases 1 and 2 are done: push every branch (if the push is denied, write the exact command for the human in GEMINI-progress.md), write "READY FOR CLAUDE REVIEW: batch 2" at the top of docs/handoffs/GEMINI-progress.md, then continue with Phase 3 without waiting.

## 6. Phase 3: the backend board, in this order, each task on its own branch stacked on your tip
1. T-023 clip pipeline and job worker (worker_jobs/finalize_clip.py is the job-handler exemplar; real upload to the local Supabase clips bucket, real ffmpeg transcode, real worker loop picking a job).
2. T-027 TTS tool and tts_hazards job (real audio written to the audio bucket, path written into the stored graph, the file plays).
3. T-021 Skill Compiler graph (LangGraph, Postgres checkpointer, review interrupt, 25-node cap, prompts verbatim from 14.3 to 14.7). There is no master clip yet (T-004 is human), so test on a short clip you generate or record yourself and say so; AC3 stays partly until the real clip exists. Free tier: bound the detail fan-out to 2 concurrent calls.
4. T-028 interviewer backend: POST /v1/skill-versions/{id}/interview and /tips (needs CR-006 approved; if not, stop this item and continue).
5. T-033 issuance API (POST /v1/credentials with eligibility and policy_not_met reasons, GET /v1/credentials/{id}) and apps/web/lib/vc/verify.ts passing the shared vectors in vitest. Claude builds the pages.
6. T-036 AC2: docs/legal/consent-notice-v1.md in Hindi and English (purpose per scope, revocation, the "models cannot unlearn" sentence, contact). AC1 (hi.json review) waits until Claude's T-012 is on main.
7. T-040 refinery deterministic pipeline (pin lerobot; the exported dataset loads with LeRobotDataset; server-side blur pass).
8. T-041 refinery agent and dataset endpoints (Claude builds the viewer).
9. T-044 dashboard endpoint over the fixed views (numbers checked against seeded data).
10. T-047 eval harness and `make usage` (real recordings are T-046, human; build and test the harness on generated runs and mark AC1 partly until they exist).
11. T-048 full seed (idempotent; uses real clips once T-004 exists, otherwise generated ones, said clearly).
Every 3 tasks, do a whole-backend pass as a judge would, with curl against the running API: demo join, start a session, verify a frame, complete, issue a credential and verify its proof, grant consent and verify the chain, build a dataset, license it, see earnings, read the dashboard. Fix whatever breaks before the next task.
When Claude merges something to main, rebase your stack: `git fetch origin && git rebase --update-refs origin/main` from the tip.

## 7. Free tier (D-011)
Budget calls: cache verifier and compiler results by input SHA-256 during development, keep live tests opt-in, and log every 429 with the time and model in docs/research/live-api.md. Never use another key or project.

## 8. Blockers: when to stop
A blocker is: an account, key, recording or decision only the human has; a CR that is not approved; the plan contradicting itself; free-tier quota exhausted for the day; the same item failing three times.
On a blocker: write it in the task's handoff and in docs/handoffs/GEMINI-progress.md (what, why, what you need, who decides), then move to the next unblocked item. Stop the loop only when no unblocked item is left in Phases 1 to 3. Never work around the spec or fake a result to get past a blocker.

## 9. Reporting
Keep docs/handoffs/GEMINI-progress.md current after every item: review finding or task id, status, branch and commit, evidence, blockers, API changes. End with the list of blockers, the exact commands to run everything, and what Claude must review first.
```
