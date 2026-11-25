# Gemini Batch 2 — Phase 0 Baseline Report

- **Date:** 2026-11-26 (IST)
- **Tip branch:** `agent/gemini/T-020-verifier-two-key` (`1c50a1d`, rebased cleanly onto `main` `356ae58` via `git rebase --update-refs main`)
- **Database used:** Real local PostgreSQL 16.15 (`127.0.0.1:5432/parampara_dev`, Homebrew; Docker daemon not running in this environment, so `supabase/config.jsonc` was initialized via `supabase init` and `db/reset.sh` emulates `anon`/`authenticated`/`service_role`, `auth.*`, and shims `vector(768)` when `pgvector` is absent while running verbatim on Supabase Docker).

## 1. `make check` on Rebased Tip (`1c50a1d`)

- **Command:** `export RUFF_CACHE_DIR=/tmp/ruff_cache && make check`
- **Result:** PASS (exit 0)
  - `ruff check .` — All checks passed
  - `ruff format --check .` — 63 files formatted
  - `mypy` — Success: no issues found in 44 source files
  - `pytest -q` — 57 passed in 1.92s
  - `pnpm lint` + `pnpm typecheck` — clean
  - `pnpm test` (vitest) — 6 test files, 20 passed
  - `gen_contracts.sh --check`, `size_check.py`, `banned_terms.py`, `gitleaks` (22 commits, 0 leaks) — all clean

## 2. `make db-reset` Wired & Executed Twice

- **Files added/updated (lane: `db/`, `supabase/`, `Makefile` `db-reset`):**
  - `supabase/config.jsonc` (`supabase init --force`, CLI v3.4.0)
  - `db/reset.sh` (auto-detects `DATABASE_URL`, local Supabase `127.0.0.1:54322`, or local Postgres `127.0.0.1:5432/parampara_dev`, applies `db/migrations/*.sql` in order, runs `db/seed/seed.py`)
  - `Makefile` `db-reset` wired to `@bash db/reset.sh`
- **Command:** `make db-reset && make db-reset`
- **Result:** Both runs exited 0 (`Applying 0001_init.sql... 0002_rls.sql... 0003_views.sql... Minimal seed applied cleanly. db-reset complete.`).

## 3. P0 Reproductions (All 8 Confirmed)

### P0-1 — Forged unsigned JWT accepted by `/v1/me`
- **Repro:** Sent `alg: none` JWT with `sub: "99999999-0000-4000-8000-000000000099"`, `roles: ["owner","supervisor","lab_buyer"]`, signature `.forged` to `GET /v1/me`.
- **Observed:** HTTP **200**:
  ```json
  {"profile":{"id":"99999999-0000-4000-8000-000000000099","display_name":"Worker","pseudonym":"worker_99999999","preferred_lang":"hi"},"memberships":[{"org_id":"10000000-0000-4000-8000-000000000002","roles":["lab_buyer","owner","supervisor"]}]}
  ```

### P0-2 — Live token without tools (real `gemini-3.8-live` session)
- **Repro:** `POST /v1/sessions` minted `auth_tokens/f4e058b4...` for `gemini-3.8-live`; connected via `genai.Client(api_key=token, http_options={"api_version": "v1alpha"})` and sent `"नमस्ते, कौन सा कदम करना है?"`.
- **Observed:** Connected and spoke Hindi (`audio_bytes=687360`, `elapsed_ms=17567`), **`tool_calls: []`** (zero calls to `get_current_step`).

### P0-3 — Verifier HTTP 400 on every real Gemini call
- **Repro:** `POST /v1/sessions/{id}/verify` with a 64×64 JPEG frame, `trigger="edge"`, `edge_summary={"edge_key": true, "checks": []}`.
- **Observed:** HTTP 200 fallback `{"status":"unavailable","confidence":0.0,"latency_ms":170,"visible_issues":["verifier_unavailable"]}`; `GET /v1/traces/recent` shows only `"summary":"verifier: failed (ClientError)"` with the real Gemini 400 (`Unknown name "additional_properties"`) hidden.

### P0-4 — Six client `completed` events give `clean_run: true`, repeated `/complete` inflates mastery
- **Repro:** Posted 6 `type="completed"` events (no `edge_key`, no `/verify` call) to `/v1/sessions/{id}/events`, then called `POST /v1/sessions/{id}/complete` 4 times.
- **Observed:**
  - Complete #1: `clean_run=True`, `eligible=True`, `s1_p_learned=0.6`
  - Complete #2: `clean_run=True`, `eligible=True`, `s1_p_learned=0.8903`
  - Complete #3: `clean_run=True`, `eligible=True`, `s1_p_learned=0.9774`
  - Complete #4: `clean_run=True`, `eligible=True`, `s1_p_learned=0.9956`

### P0-5 — `anon` reading `v_earnings` (views bypass RLS)
- **Repro:** Inserted a `royalty_events` row (`32500` paise for Ramesh) in a transaction, ran `SET LOCAL ROLE anon; SELECT * FROM v_earnings;`.
- **Observed:** Returned `20000000-0000-4000-8000-000000000001 | 32500 | | 1` (full earnings exposed to `anon`).

### P0-6 — `TRUNCATE consent_records CASCADE` succeeds as `authenticated`
- **Repro:** In a transaction on `parampara_dev`, ran `SET LOCAL ROLE authenticated; TRUNCATE consent_records CASCADE;`.
- **Observed:** `TRUNCATE TABLE` succeeded (`NOTICE: truncate cascades to table "dataset_episodes"`).

### P0-7 — User B granting consent on User A's clip
- **Repro:** Authenticated as `demo:user_b`, called `POST /v1/consents` granting `robotics_commercial` on `clip_id: "99999999-0000-4000-8000-000000000001"`.
- **Observed:** HTTP **200**, appended `seq=1` (`hash=c5278d2d...`) without checking clip ownership.

### P0-8 — Zero-byte default issuer seed published by `/.well-known/did.json`
- **Repro:** Started app with `ISSUER_ED25519_SEED_B64=""` and called `GET /.well-known/did.json`.
- **Observed:** HTTP **200**, `publicKeyMultibase: "z6MkiTBz1ymuepAQ4HEHYSF1H8quG5GLVVQR3djdX3mDooWp"`, which matches `encode_public_multikey(Ed25519PrivateKey.from_private_bytes(bytes(32)).public_key())` (`True`).

## 4. Additional Observations

- FastAPI validation errors on malformed bodies currently return FastAPI's default `{"detail": [...]}` rather than `ApiError` (already tracked under P1 API contract).
- Sandbox note: `curl` to `127.0.0.1` is blocked by host policy in this environment; all API reproductions were verified against the real FastAPI ASGI app (`httpx.ASGITransport`) and real PostgreSQL 16 (`psql`/`psycopg`) + real Gemini free-tier endpoints (`google-genai`).
