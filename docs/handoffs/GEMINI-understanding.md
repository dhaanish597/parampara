# Parampara — Gemini Lead Builder Understanding

Date: 2026-11-26 IST
Worktree: `../pp-gemini`

## 1. Product in My Own Words

**Parampara** (परम्परा) is a phone-first platform for Indian manufacturing and vocational training (BUILD 2036, Frontier 04: Manufacturing Renaissance) that turns a single master worker's narrated demonstration into a closed five-stage loop (**Capture → Coach → Certify → Consent → Compensate**):

1. **Capture (Skill Compiler + Tacit Interviewer):** A master worker records a 1–3 minute top-down demonstration on a phone while narrating in Hindi/Hinglish (with faces blurred on-device). A LangGraph multi-agent pipeline segments the clip, extracts reference keyframes, writes camera-checkable success predicates, deterministic edge checks, and hazard rules, lints and critiques the draft, generates a bilingual skill card, and runs a short Hindi voice interview with the master to capture tacit "why" tips. A supervisor reviews and approves the versioned Skill Graph.
2. **Coach (Live Ustaad Coach + On-Device Edge Engine + Two-Key Verifier + BKT Mastery):** A trainee mounts their phone over an unpowered bench, calibrates zones (tap) and parts (colour sampling with overlap check), and performs the task under a live Hindi AI coach (Gemini Live over WebSocket with single-use ephemeral tokens). On-device MediaPipe Hands + HSV colour rules fire local pre-error interrupts ("Ruko!") in under 300 ms without waiting for the cloud. A Bayesian Knowledge Tracing (BKT) engine fades coaching scaffolds across `full → hint → watch → exam` modes.
3. **Certify (Proof-of-Skill Credentials):** Once a trainee meets the skill's `CredentialPolicy` (mastery threshold, consecutive clean runs, optional exam mode) and a supervisor co-signs, Parampara issues a W3C Verifiable Credential 2.0 signed with Ed25519 Data Integrity (`eddsa-jcs-2022`) under `did:web:<domain>`, containing a SHA-256 Merkle root of private evidence clip/frame hashes. Anyone can scan the QR code to verify it in-browser at `/verify/[id]` and run a 1-click tamper test.
4. **Consent (Consent Wallet & Hash-Chained Ledger):** Clips default to private. Workers listen to a plain-Hindi notice, pass a comprehension question ("can you revoke anytime?"), choose granular scopes (`train_own_org`, `train_other_employers`, `robotics_research`, `robotics_commercial`) and optional expiry, and can revoke anytime. Every grant/revoke appends to a tamper-evident SHA-256 hash-chained Postgres ledger (`consent_records` with locked `consent_chain_head`).
5. **Compensate (Data Refinery + Licensing + Royalties):** Consented sessions (plus error/recovery annotations captured naturally during coaching) are refined into `LeRobotDataset v3.0` episodes with 128-float hand-pose state/action vectors and a second server-side face-blur check. Robotics labs license datasets under immutable no-surveillance/no-biometrics terms; effective consent is re-checked at export and again at licence time. Revenue splits deterministically in integer paise (25% platform, 10% factory, 65% worker pool: 50% master [with 25% lineage share to parent master if forked], 40% trainees pro-rata by episodes, 10% reviewer) and triggers test-mode UPI payouts (`razorpayx_test` or `simulated`).

A **Factory Command Centre (`/dashboard`)** surfaces the skill matrix (learning status only), time to competency, mistake hotspots, issued credentials, data earnings, and agent activity—never individual worker speed or productivity rankings.

The demo skill driving all acceptance tests is **3-way terminal block wiring on a DIN rail** (6 steps: check ferrules, earth green→PE, neutral black→N, phase red→L, tighten screws, pull test; critical hazard M1: phase wire near N terminal).

---

## 2. Architecture

Five strict layers with explicit boundaries:

1. **Phone Edge (`apps/web`, Next.js PWA):**
   - `lib/edge/`: Camera, MediaPipe `HandLandmarker` & `FaceDetector` (~15 fps), pure HSV colour matching & calibration (`colour.ts`, `calibrate.ts`), pure frame features (`features.ts`), pure dwell/cooldown rules (`rules.ts`), on-device face blur (`blur.ts`), and `MediaRecorder` (`recorder.ts`). Pure modules never import browser APIs so they are unit-testable in Vitest.
   - `lib/live/`: `@google/genai` Live WebSocket client (`client.ts`) using single-use ephemeral tokens, 16 kHz PCM16 mic capture (`mic.ts`), 24 kHz PCM16 playback with ducking/interrupt flush (`speaker.ts`), 1 fps 768×768 JPEG frames (`frames.ts`), local tool router answering all 5 coach tools in <50 ms (`tools.ts`), captions (`captions.ts`), and `config.ts`.
   - `lib/coach/`: Finite state machine (`machine.ts`) managing calibration, coaching, two-key window, event batching (2 s), reconnection with resumption handles, and `SCRIPTED_FALLBACK`.
   - `lib/vc/`: In-browser `eddsa-jcs-2022` verification (`verify.ts`) using `@noble/ed25519`, `canonicalize`, and `bs58`.
2. **Real-Time AI Session:** Gemini Live API (`MODEL_LIVE`, default `gemini-3.8-live`) with context-window sliding compression and session resumption, locked via backend-minted ephemeral tokens.
3. **Backend API & Job Worker (`services/api`, FastAPI + Python 3.12 + uv):**
   - `api/`: REST `/v1` routes, Supabase JWKS JWT auth, explicit `require_role` checks, `ApiError` envelope with `request_id`, rate limits, idempotency keys, SSE trace stream (`/v1/traces/stream`).
   - `agents/llm.py`: Single LLM gateway for all non-Live calls (`MODEL_FLASH`, `MODEL_LITE`, `MODEL_TTS`), structured Pydantic output with 1 schema-repair retry, backoff retries, `<<<USER_TEXT ... USER_TEXT>>>` prompt-injection wrapping, `model_calls` DB logging, Langfuse spans, and `trace_events`.
   - `agents/`: Versioned prompt files (`prompts/*.md`) for Skill Compiler (`compiler/` LangGraph with `PostgresSaver` and supervisor review interrupt), Tacit Interviewer (`interviewer/`), Live Coach builder/token minter (`coach/`), Verifier (`verifier/`), and Refinery (`refinery/`).
   - `worker.py` & `worker_jobs/`: Async Postgres `FOR UPDATE SKIP LOCKED` job queue (max 2 concurrent, 3 retries with 5 s / 30 s / 120 s backoff) handling `finalize_clip`, `compile_skill`, `tts_hazards`, and `build_dataset`.
4. **Deterministic Trust Services (`services/api/src/parampara/tools/`):** Pure, LLM-free, exhaustively tested modules: `hashing.py`, `skill_lint.py`, `keyframes.py`, `bkt.py`, `jcs.py`, `multikey.py`, `vc.py`, `merkle.py`, `ledger.py`, `scopes.py`, `royalty.py`, `payouts.py`, `tts.py`.
5. **Data, Storage & Observability (`db/`, local Supabase Docker -> hosted Supabase later):** Postgres 15+ with `pgcrypto`, `pgvector`, RLS on every table (`0002_rls.sql`), dashboard views (`0003_views.sql`), private Storage buckets (`clips`, `frames`, `audio`, `datasets`), Langfuse + `model_calls`/`trace_events`.
   - **Active operational constraints:** Gemini stays on **free tier only** (D-011); API+worker hosting switches from Cloud Run to **Render free web service** (CR-001); Supabase uses **local Docker** until a hosted project slot is freed.

---

## 3. The Two-Key Rule

The core design invariant is: **agents perceive, reason, and talk; deterministic tools measure, sign, and enforce; a verifier signs off before anything counts.**

Specifically, for a step `s` to become `completed`:
1. **Edge key:** The on-device deterministic edge engine emits `edge_key` for `s` (e.g., `part_in_zone` dwell ≥ `min_dwell_ms` with no hand in zone).
2. **VLM key:** The server-side Verifier agent (`MODEL_FLASH`, 8 s timeout) evaluates a hi-res (1280 px) frame against the reference keyframe and step predicates and returns `VerifierVerdict` with `status == "pass"` and `confidence >= 0.7`.
3. **5-second window:** Both keys must agree within 5 seconds of each other (verification triggers on whichever arrives first: edge key or coach's `request_step_check`; only one verify request per step may be in flight).
4. **Special assurances:**
   - If a step's only edge check is `hands_settled`, it completes with `single` assurance (still counts toward credential, shown transparently in summary).
   - After two `unavailable` verifier responses on a step, a supervisor (or judge in demo mode) can manually confirm (`manual` assurance), which explicitly marks the run **not clean**.
5. **No LLM autonomy:** The Live coach can *never* mark a step done on its own; only a `[SYSTEM]` message after both keys pass advances the step. Similarly, no LLM output alone issues a credential, writes consent, or moves money.

---

## 4. Safety, Privacy & Governance Rules (Never Break)

1. **No surveillance or biometrics:** Zero face recognition, biometric identification, individual productivity scoring, idle-time tracking, or worker ranking/leaderboards. Enforced by `scripts/banned_terms.py` and `tests/test_no_surveillance.py`. Every data licence hard-codes `no_individual_productivity_scoring: true` and `no_biometric_identification: true`.
2. **Double face-blur guarantee:** Faces and bystanders are blurred on-device via MediaPipe FaceDetector (20% padding) before recording/upload; unblurred video never leaves the phone. The refinery runs a second server-side face-blur check before dataset export.
3. **Consent by default private & revocable:** Every clip starts private. Sharing requires Hindi notice audio + comprehension check + explicit scope selection written to an append-only hash-chained ledger (`consent_records`, no UPDATE/DELETE). Effective scopes are re-checked at dataset export and again at licence purchase. Revocation stops future exports/licences (and transparently states trained models cannot unlearn).
4. **Data minimisation:** Credentials and datasets use pseudonyms (`urn:parampara:worker:<pseudonym>`), never phone numbers or Aadhaar. `upi_vpa` is masked and used only for payouts. Credentials store SHA-256 Merkle roots, never video.
5. **Electrical safety:** Training benches are never powered. Skill cards warn "Never practise on powered circuits." The Live coach refuses live electrical advice.
6. **Secrets & browser isolation:** Secrets live only in `.env` / secret stores; never printed or committed (`gitleaks` in `make check`). The browser never receives `GEMINI_API_KEY`—only single-use ephemeral tokens with locked constraints.
7. **Test-mode payouts only:** No real money moves (`razorpayx_test` or `simulated`), always labelled "Test mode. No real money moved."
8. **Code & contract integrity:** Never edit `contracts/schemas/`, `AGENTS.md`, `CLAUDE.md`, `docs/BUILD_PLAN.md`, or the quality gate directly—open a CR in `docs/CHANGES.md`. Never merge or push to `main`. Files ≤ 300 lines, functions ≤ 40 lines, no model IDs outside `settings.py` and `lib/live/config.ts`, all user-facing strings through i18n with Hindi.

---

## 5. Spec Gaps & Discrepancies Noticed

1. **`SessionSummary` / `StepOutcome` schema vs. prose in `BUILD_PLAN.md` (16.7, 17.4, 18.1, 18.3):**
   - Prose specifies recording `coach: "scripted"` (16.7) and `edge_fps` (17.4) in the session summary, and `assurance: "single" | "manual"` on step outcomes (18.1, 18.3).
   - `contracts/schemas/session-summary.schema.json` enforces `"additionalProperties": false` and omits `coach`, `edge_fps`, and `assurance` (only `two_key: boolean` exists on `StepOutcome`). Needs a CR if these fields are to live inside `SessionSummary`, or they must be stored in `step_events` / separate session columns.
2. **Tacit Interviewer endpoint path vs. `skill_versions` creation timing (12.2, 14.2, 15.1):**
   - Section 15 runs the interview on a draft that is `awaiting_review`, calling `POST /v1/skill-versions/{id}/interview` and `/tips`.
   - Section 14.2 only creates a `skill_versions` row in `finalize` (after approval); before approval the draft only exists in `compile_runs.draft_graph`. We should either create a `status='draft'` `skill_versions` row when `compile_skill` hits `awaiting_review`, or open a CR to clarify whether `{id}` can also resolve a `compile_run_id`.
3. **`Idempotency-Key` persistence missing from `0001_init.sql` (12.1 vs. 11.1):**
   - Section 12.1 mandates storing `Idempotency-Key` with ledger and licence records, but `consent_records` and `licences` in 11.1 have no `idempotency_key` column (nor an `idempotency_keys` table). A dedicated `idempotency_keys` table (or columns in `0001_init.sql`) is needed in T-010.
4. **Fixture vs. spec minor mismatches in `contracts/fixtures/`:**
   - `consent-record.json` uses `"notice_version": "v1"` (spec 21.1 says `"consent-notice-v1"`).
   - `credential.json` uses `"id": "did:example:trainee"` (spec 20.1 says `urn:parampara:worker:<pseudonym>`) and context URL `"https://parampara.app/contexts/skill/v1"` (spec 7/30.1 puts the static file at `/contexts/skill/v1.jsonld`).
5. **Generated TypeScript empty-object types in `packages/contracts/src/generated/index.ts`:**
   - `ApiError.error.details`, `SessionStartResponse.live.config`, and `StepEvent.payload` generated as `{}` in TS (while Python generated `dict[str, Any]`) because their schemas specify `"type": "object"` without `"additionalProperties": true`. Callers in TS will need care or a CR to add `"additionalProperties": true` on those three open map fields.
6. **CR-001 (Render) & D-011 (Free-tier Gemini) vs. `BUILD_PLAN.md` v1.0:**
   - `BUILD_PLAN.md` has not yet been bumped to v1.1 for CR-001 (Render instead of Cloud Run) or D-011 (free-tier Gemini instead of paid tier in 9.1). T-003 will empirically test free-tier limits for Live video sessions, TTS, Flash, and Flash-Lite and raise a CR if any plan assumption (e.g. 6-minute 1-fps video session or parallel compiler fan-out) hits free-tier caps.
7. **Endpoints without JSON Schemas in `contracts/schemas/`:**
   - Routes like `GET /v1/me`, `POST /v1/clips`, `POST /v1/skills`, `GET /v1/skill-versions/{id}`, `GET /v1/orgs/{id}/dashboard`, `GET /v1/earnings/me`, `GET /v1/consents/verify-chain`, and `GET /v1/admin/usage` rely on FastAPI Pydantic response models + OpenAPI codegen (`openapi-typescript`) rather than `contracts/schemas/`.
8. **Human-blocked tasks:**
   - `T-000` (accounts/registration/kits), `T-004` (real master & practice clips), `T-026` (prompt tuning on T-004 clips), `T-046` (30 real eval runs), `T-052` (final demo video & submission) require human action or physical bench recordings.
