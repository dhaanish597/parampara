# Review of Gemini batch 1 (12 stacked branches, tip 43e5bf9)

- Reviewer: Claude Code (lead), 2026-11-26, with three focused sub-reviews (database, edge and two-key, trust tools).
- Scope: every file changed on `agent/gemini/T-003-live-spike` through `agent/gemini/T-020-verifier-two-key` against `main` (95441a0), checked against `docs/BUILD_PLAN.md`.
- Verdict for every branch: **CHANGES**. Nothing merges until the P0 items below are fixed and re-verified.

## How this was verified (behaviour, not only tests)

| Check | Result |
| --- | --- |
| `make check` on the tip | Green. 57 pytest, 20 vitest, ruff, mypy, eslint, tsc, size, banned terms, gitleaks. |
| API started with `uvicorn` and called with `curl` | Ran. Auth, session, verify, consent and trace routes exercised. |
| Real Gemini Live: token from `POST /v1/sessions`, connected the way the browser will | Connects and speaks Hindi, but **never calls a tool** (see P0-2). |
| Real Gemini verifier through `POST /v1/sessions/{id}/verify` | **Fails on every call** with HTTP 400 from Gemini, returned to the client as `unavailable` (see P0-3). |
| Migrations applied to a real Postgres 16 with a minimal Supabase emulation (pgvector stubbed) | Apply cleanly; seed idempotent; RLS mostly right; real holes found (see P0-5, P0-6). |
| Independent re-implementations: VC signing, JCS, Merkle, ledger hash, royalty split (20,000 random cases), BKT | All match. The pure maths is good. |
| Adversarial edge-engine and two-key probes (irregular timestamps, boundaries, reorderings) | Core timing correct; several state bugs (see P1). |

## What is genuinely good

- Pure maths is correct and well tested: `royalty.py` (exact 23.2 case, rounding rule), `bkt.py` (19.1 equations, mode thresholds), `merkle.py`, `jcs.py`, `vc.py` signing (independent signature matches), ledger canonical record and hash, `skill_lint.py` (all 10 codes fire), `keyframes.py` on a real ffmpeg video.
- Edge engine timing is right: dwell is time-based, cooldowns 3 s and 5 s, red hue wrap, dark-part rule, calibration tolerances exactly per 17.3. Benchmark about 0.1 ms per frame on desktop.
- Two-key window is right at the boundaries (5000 ms passes, 5001 fails; confidence 0.70 passes, 0.69 fails) and uses frame time, not arrival time.
- Schema in `0001_init.sql` is identical to 11.1 (compared with `pg_dump -s`). Trainee isolation, own-only consent reads, client-blocked tables, append-only trigger on UPDATE and DELETE all work on a real database.
- T-003 research is useful: v1alpha token minting, thinking config must be omitted on `gemini-3.8-live`, TTS needs v1beta and returns WAV, a fresh token is needed to resume.
- Handoffs, commit trailers and the spec-gap list in `GEMINI-understanding.md` are well done.

## The core problem

Most of the backend is a demo shell around correct pure functions. Sessions, mastery, consents and telemetry live in Python dicts and vanish on restart. Auth trusts unsigned tokens. Several handoffs tick an AC that the code does not meet, because the tests mock the part that is broken (the verifier test mocks Gemini, so the real 400 was never seen; the migration test checks strings, so nothing was applied).

## P0: must fix before any merge (security, safety rules, broken core)

| # | Where | Problem (observed) | Fix |
| --- | --- | --- | --- |
| P0-1 | `api/deps.py:34-80` | JWTs are decoded without verifying the signature. A hand-made token with any `sub` and `"roles": ["owner","supervisor","lab_buyer"]` was accepted by `/v1/me`. Any `Bearer demo:<anything>` token is a user; `demo/join` then grants all five roles. Memberships come from the token and an in-memory dict, never from `memberships`. | Verify against Supabase JWKS (12.1), load profile and memberships from the DB, keep demo join as a DB insert for anonymous Supabase users only. Remove the `demo:` token path from non-test code. |
| P0-2 | `agents/coach/token.py:26-49` | The token's locked Live config has **no tools**, and `live_config_dict` is ignored. Real test: the coach greeted in Hindi but never called `get_current_step`, even when the client also sent tools. With tools locked into the token (my probe), the coach called `get_current_step` at 2.1 s. The spike passed only because `probe_live.py` used a different config. | Build the token's `LiveConnectConfig` from `build_live_connect_config` (one source), including tools and `realtimeInputConfig`. Add a test that the token config and the 16.3 config are the same. |
| P0-3 | `agents/llm_helpers.py:78-84` | Every structured call fails: Gemini returns 400 `Unknown name "additional_properties"` because Pydantic models with `extra="forbid"` are passed as `response_schema`. The verifier swallows the error and the trace says only `failed (ClientError)`. Real call with `response_json_schema=Model.model_json_schema()` worked: verdict `pass`, 0.95. | Use `response_json_schema`. Log the exception message in the `error` trace and in `model_calls.error`. Add one opt-in live test (`-m live`) per structured agent. |
| P0-4 | `db/repos/sessions.py:70`, `api/routes/sessions.py:160` | Two-key rule broken server-side: `two_key = two_key or completed`. Real test: posting six client `completed` events with no edge key and no verify call gave `clean_run: true`, `credential_eligible: true`. Calling `/complete` three more times raised mastery 0.60, 0.89, 0.98, 0.996 (one session fakes a streak). | Server decides: `two_key` only from a stored `vlm_key` (written by `/verify`) plus an `edge_key` within 5 s. Client `completed` is a claim, not proof. `/complete` is idempotent (return the stored summary). Aborted sessions are not runs. |
| P0-5 | `db/migrations/0003_views.sql` | All four views bypass RLS: `anon` read every user's earnings from `v_earnings`; a trainee of another org read the demo org's matrix and hotspots. | `with (security_invoker = true)` and revoke from `anon`, `authenticated`; serve the dashboard through the API. |
| P0-6 | `db/migrations/0002_rls.sql:20-22` | `truncate consent_records cascade` succeeded as `authenticated` and as `anon` (the trigger is row-level only). The ledger is not append-only. | Revoke TRUNCATE (and browser insert, update, delete) from `anon`, `authenticated`, `service_role`; add a statement-level `before truncate` trigger. |
| P0-7 | `api/routes/consents.py:19-45`, `tools/scopes.py:21-37` | Anyone can grant or revoke consent for any clip or session: user B granted `robotics_commercial` on a random clip and it became effective. Scopes never check that the record's subject owns the target. | Check ownership of the target before append; count only records whose subject is the owner. |
| P0-8 | `api/settings.py:22,50,63` | Issuer seed defaults to 32 zero bytes, a public key; an empty env value silently falls back to it, and `/.well-known/did.json` publishes it. Any deploy without the secret issues forgeable credentials. | Fail at startup when the seed is missing and `APP_ENV != local`; random per-process key in local. |

## P1: plan conformance and correctness

**Persistence (T-011, T-016, T-020, T-034).** Sessions, events, calibration, mastery, runs, consents, `model_calls` and `trace_events` are in-memory. No `db/pool.py`, no repos except a read-only `skill_versions` that falls back to the fixture when `DATABASE_URL` is empty. No Langfuse at all (T-011 AC3). The consent "row lock" is an `asyncio.Lock`; the 21.2 transactional append on `consent_chain_head` is not implemented (T-034 AC1 not met). Fix: `db/pool.py`, repos for sessions, step events, mastery, consents, telemetry; trace bus mirrors to `trace_events`; DB-backed tests against a local Postgres.

**Verifier (T-020 AC1).** Frame is hashed but not stored in `frames`; the reference keyframe is never loaded; worst case is about 34 s (8 s per attempt x retries x schema repair), not 8 s; no check that `predicate_results` covers every predicate. The one real call took **11.1 s** on the free tier, over the 8 s budget and the 5 s two-key window. Fix: one overall 8 s deadline; store frame; load keyframe; deterministic predicate coverage check. Measure 10 calls with thinking at its lowest setting and with `gemini-3.5-flash-lite`, and raise a CR if the budget cannot hold.

**API contract.** `/verify` returns `pass_` instead of `pass` (dump without `by_alias=True`). FastAPI validation errors return `{"detail": ...}`, not `ApiError`; unhandled errors are bare 500s. `/v1/admin/usage` has no auth. `/v1/traces/stream` and `/recent` have no org check. No rate limits (12.1). Hard-coded `"Ramesh (demo)"` and demo UUIDs in core code (`routes/sessions.py`, `repos/skill_versions.py`, `settings.py`). Upload URL is a fake `/api/local-upload/` path; hazard audio URLs are empty strings. The `prompt_version: coach-1` line is sent to the model inside the system instruction.

**Licences and earnings (T-042).** `POST /v1/licences`, `GET /v1/licences/{id}/download`, `GET /v1/earnings/me` do not exist; `split_royalties`, `create_payout` and `payout_provider` have no caller. `split_royalties` crashes with zero trainees (`IndexError`) and accepts negative episode counts. `razorpayx_test` is a stub that returns `queued` without calling anything. T-042 AC2 ticked but not met.

**Credentials (T-031, T-032).** `verify_credential` accepts a proof whose `cryptosuite`, `type`, `proofPurpose` or `verificationMethod` was changed and re-signed; add those checks and negative vectors. `EVIDENCE_QUERY_SQL` includes non-clean runs and frames from every event type; restrict to the counted runs and `vlm_key` frames.

**Consent route.** Accepts unknown `notice_version`, empty-scope grants, past `expires_at`, both targets at once, revoke with nothing to revoke; no `Idempotency-Key`. `effective_scopes` ignores a later, shorter-lived re-grant.

**Edge engine and two-key (T-013, T-020 AC2).**
1. `rules.ts:36,57` `firedEdgeKeys` is never cleared: after a two-key window expires the step can never get a new edge key (deadlock). Add re-arm on expiry or step re-entry.
2. `hands_settled` fires with no hands in view (motion is 0 when hands are missing).
3. Motion pairs hands by array index; a swapped order gives motion 0.6 on still hands. Match by handedness.
4. Zone circles are circles in pixels for colour but ellipses in normalised units for hand-in-zone and pinch distance (1.78x wider on 16:9). Use `frame_w`, `frame_h`.
5. Any `min_dwell_ms` or `min_ms` above 3000 can never fire (3 s buffer prune).
6. `out_of_order` still fires after the current step is verified.
7. `twoKey.ts` has no current-step gating; assurance can flip from `two_key` to `single` after completion; manual confirm counts non-consecutive `unavailable` and can overwrite a completed step; no in-flight or timeout signal.
8. Coverage was never measured (`@vitest/coverage-v8` missing) and the benchmark test uses no hands.

**Database.** `datasets` and `dataset_episodes` visible to every lab buyer, owner and supervisor of any org. `is_member` is `SECURITY DEFINER` without `search_path`. `v_skill_matrix` reports `exam_ready` when only some steps have mastery rows. `payouts_select` lacks the org-owner branch. `make db-reset` is still `exit 1` and there is no `supabase/` config. `test_db_migrations.py` checks strings only.

**T-003.** Not run on a phone. Resume was tested with the raw API key, not a fresh ephemeral token. Free-tier limits are quoted as "typical", not measured. A 6-minute session was not run. The plan's `give_hint` declaration uses an integer `enum`, which Gemini's schema rejects (plan bug, CR below).

## P2: polish

`skill_lint` at 95% branch, not 100% (T-022 AC1); duplicate ids not linted; `keyframes.py` allows `../` in step ids; tools read the clock and randomness (inject them); missing docstrings; hidden defaults (radius 0.07, `min_ms` 400) in `rules.ts`; `circularMedianHue` is a mean; `v_step_hotspots.error_rate` can exceed 1; no indexes on RLS columns.

## Task status after review

| Task | AC status | Board |
| --- | --- | --- |
| T-003 | AC1 partly, AC2 partly, AC3 met, AC4 met | changes |
| T-010 | AC1 partly, AC2 partly, AC3 met | changes |
| T-011 | AC1 met, AC2 not met, AC3 not met, AC4 met (in-memory) | changes |
| T-013 | AC1 met, AC2 partly, AC3 partly | changes |
| T-016 | AC1 partly, AC2 met, AC3 not met (no persistence) | changes |
| T-020 | AC1 not met, AC2 partly, AC3 not started | changes |
| T-022 | AC1 partly, AC2 met, AC3 met | changes |
| T-030 | AC1 met, AC2 partly, AC3 met | changes |
| T-031 | AC1 partly, AC2 partly | changes |
| T-032 | AC1 met, AC2 partly | changes |
| T-034 | AC1 not met, AC2 met, AC3 partly | changes |
| T-042 | AC1 partly, AC2 not met, AC3 partly | changes |

## Decisions and change requests needed (human and Claude)

1. **CR-003** `give_hint.level`: replace `"enum": [1, 2, 3]` with `"minimum": 1, "maximum": 3` in 16.5. Verified against the live API.
2. **CR-004** Live reconnect: add `POST /v1/sessions/{id}/live-token` that mints a fresh single-use token carrying the saved resumption handle (16.2, 16.6).
3. **CR-005** Contracts: add `assurance` (`two_key` | `single` | `manual`) to `StepOutcome`, and `coach` and `edge_fps` to `SessionSummary` (Gemini spec gap 1).
4. **CR-006** Interviewer before approval: create a `skill_versions` row with status `draft` when a compile run reaches `awaiting_review` (Gemini spec gap 2).
5. **CR-007** Record the `idempotency_keys` table in 11.1 and add a request hash column.
6. Royalty with zero trainees: where does the 40% trainee pool go? Proposal: to the master. Needs a DECISIONS entry.
7. Verifier latency on the free tier (11.1 s measured once): measure properly first; if over budget, choose between a lighter model, a larger two-key window, or both.
