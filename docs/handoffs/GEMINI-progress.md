READY FOR CLAUDE REVIEW: batch 2

# Gemini Backend Progress — Batch 2 (Phases 0–2 Complete)

- **Worktree**: `/Users/dhaanish/Documents/pp-gemini`
- **Base `main`**: `20f58e0` (`docs(tasks): T-012 done`)
- **Tip branch**: `agent/gemini/T-020-verifier-two-key` (`885d03d`)
- **Quality gate**: `make check` passed on **all 12 branches** (`ruff check`, `ruff format --check`, `mypy` 54 files, `pnpm lint`, `pnpm typecheck`, `pytest` 74 passed / 1 skipped live-Gemini on real local Supabase `54322`, `vitest` 14 files / 45 tests, `size_check.py`, `banned_terms.py`, `gitleaks`).
- **Push note**: Sandbox denies remote `git push`. Push all 12 branches from a local shell with:
  ```bash
  cd /Users/dhaanish/Documents/pp-gemini
  git push --force-with-lease origin \
    agent/gemini/T-003-live-spike \
    agent/gemini/T-013-edge-pure \
    agent/gemini/T-022-compiler-tools \
    agent/gemini/T-031-vc-tools \
    agent/gemini/T-032-merkle \
    agent/gemini/T-010-db-migrations \
    agent/gemini/T-011-api-skeleton \
    agent/gemini/T-030-mastery-bkt \
    agent/gemini/T-034-consent-ledger \
    agent/gemini/T-042-royalties-payouts \
    agent/gemini/T-016-sessions-coach \
    agent/gemini/T-020-verifier-two-key
  ```

## Stack (12 branches, autosquashed onto `main` `20f58e0`)

1. `0aaa129` `agent/gemini/T-003-live-spike` — Live API/TTS spike + 2026-11-26 429/503 log in `docs/research/live-api.md`.
2. `b3f79f2` `agent/gemini/T-013-edge-pure` — Pure edge modules (`colour`, `calibrate`, `features`, `rules`) with all P1 fixes (handedness-matched motion, aspect-ratio pixel circles, `rearmStep` + 5 s auto re-arm, `hands_settled` requires hand in view, dynamic buffer window > 3 s, skip `out_of_order` once verified) + `@vitest/coverage-v8` (`99.47%` lines across `apps/web/lib/edge/*`).
3. `0295a41` `agent/gemini/T-022-compiler-tools` — `skill_lint` (including approved CR-009 `step_without_edge_check`), `keyframes` (with path-traversal guard), `assemble`.
4. `13fa8d0` `agent/gemini/T-031-vc-tools` — `eddsa-jcs-2022` signing/verification with proof metadata & `verificationMethod` checks.
5. `99ed148` `agent/gemini/T-032-merkle` — `sha256-merkle-v1` with `EVIDENCE_QUERY_SQL` restricted to clean completed runs and `vlm_key` frames.
6. `2da6018` `agent/gemini/T-010-db-migrations` — Core schema (including approved CR-007 `idempotency_keys.request_sha256`), RLS, views, minimal seed; verified on real local Supabase `54322` with real `pgvector`.
7. `bac91cc` `agent/gemini/T-011-api-skeleton` — Real `psycopg_pool.AsyncConnectionPool` lifespan, `ApiError` for 422/HTTP/500, Postgres-mirrored `TelemetryBus` + Langfuse sink, Supabase Storage helper (`tools/storage.py`), `idempotency.py` (CR-007 409 + 24h TTL purge), Pydantic `response_model` on all routes.
8. `e0b7bf0` `agent/gemini/T-030-mastery-bkt` — BKT mastery, mode selection, eligibility (updated for CR-005 `StepOutcome.assurance`).
9. `2d609ef` `agent/gemini/T-034-consent-ledger` — Transactional `SELECT ... FOR UPDATE` on `consent_chain_head`, `Idempotency-Key` support, verified with 2-connection concurrency test on Supabase `54322`.
10. `5ac7d74` `agent/gemini/T-042-royalties-payouts` — Fixed zero-trainee & negative-episode edge cases; added `db/repos/licences_db.py` and `api/routes/licences.py` (single-transaction licence + royalty splits + test payouts + `Idempotency-Key`).
11. `88b9257` `agent/gemini/T-016-sessions-coach` — Postgres-persisted sessions/calibration/events/mastery/runs, real master name from `profiles`, CR-003 `give_hint.level` (`min 1, max 3`), CR-004 `POST /v1/sessions/{id}/live-token` (6/min rate limit), CR-005 `SessionSummary` (`assurance`, `coach`, `edge_fps`).
12. `885d03d` `agent/gemini/T-020-verifier-two-key` — Verifier CR-008 fallback (`MODEL_FLASH` 4 s -> `MODEL_LITE` inside 8 s deadline, `max_retries=0`), deterministic predicate coverage enforcement, Supabase Storage frame upload & keyframe lookup, `twoKey.ts` P1 fixes (`98.29%` lines), real Supabase DB persistence tests (`test_persistence_db.py`), and `docs/research/verifier-latency.md`.

## API Changes (for `pnpm --filter @parampara/web gen:api`)

All routes below declare explicit Pydantic `response_model`s and return `ApiError` on all 4xx/5xx/422 errors:
- `GET /v1/health` -> `HealthResponse`
- `GET /.well-known/did.json` -> `DidDocumentResponse`
- `GET /v1/me` -> `MeResponse`
- `POST /v1/demo/join` -> `DemoJoinResponse`
- `GET /v1/skill-versions` -> `list[SkillVersionSummary]`
- `GET /v1/skill-versions/{skill_version_id}` -> `SkillVersionDetail`
- `GET /v1/traces/recent` -> `list[TraceEvent]` (org/session scoped, reads Postgres)
- `GET /v1/traces/stream` -> SSE `text/event-stream` (org/session scoped)
- `GET /v1/admin/usage` -> `UsageResponse` (requires `owner`/`supervisor`)
- `POST /v1/consents` -> `ConsentRecord` (supports `Idempotency-Key` with 409 on hash mismatch)
- `GET /v1/consents/me` -> `list[ConsentRecord]`
- `GET /v1/consents/verify` -> `ConsentVerifyResponse`
- `POST /v1/sessions` -> `SessionStartResponse`
- `POST /v1/sessions/{session_id}/live-token` -> `LiveTokenRefreshResponse` (CR-004, 6/min rate limit)
- `POST /v1/sessions/{session_id}/calibration` -> `OkResponse`
- `POST /v1/sessions/{session_id}/events` -> `EventsAcceptedResponse`
- `POST /v1/sessions/{session_id}/complete` -> `SessionSummary` (accepts `status`, `clip_id`, `coach`, `edge_fps`)
- `GET /v1/sessions/{session_id}` -> `SessionDetailResponse`
- `POST /v1/sessions/{session_id}/verify` -> `VerifierVerdict`
- `POST /v1/licences` -> `CreateLicenceResponse` (supports `Idempotency-Key` with 409 on hash mismatch)
- `GET /v1/licences/{licence_id}/download` -> `LicenceDownloadResponse`
- `GET /v1/earnings/me` -> `EarningsResponse`

## Real Verification Summary

- **Real local Supabase (`127.0.0.1:54322`)**: `make db-reset` clean; `test_persistence_db.py` 4/4 passed (pool lifecycle + telemetry mirroring, 2-connection `FOR UPDATE` consent concurrency, session + consent + 422 `ApiError` + fresh-app reload, licence + `Idempotency-Key` replay/409 + download + earnings); `test_db_migrations.py` live RLS/view/search_path tests passed.
- **Real Gemini Free Tier**: 10-call-per-variant study recorded in `docs/research/verifier-latency.md` (`flash-lite` p50 `3,751 ms`, p95 `5,583 ms`; `flash` 10/10 429 logged in `docs/research/live-api.md`); `RUN_LIVE=1 pytest tests/test_verifier.py` passed 6/6 in `6.12 s` via CR-008 fallback.
- **Pure TS Coverage (`@vitest/coverage-v8`)**: `apps/web/lib/edge/*` **99.47% lines** (`100%` functions), `apps/web/lib/coach/twoKey.ts` **98.29% lines** (`100%` functions).

---
Proceeding immediately into **Phase 3** (T-023 -> T-027 -> T-021 -> T-028 -> T-033 -> T-036 AC2 -> T-040 -> T-041 -> T-044 -> T-047 -> T-048) stacked on `agent/gemini/T-020-verifier-two-key`.
