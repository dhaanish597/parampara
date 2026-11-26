# CHANGES.md: change requests to the plan and contracts

Anyone may propose. The human and Claude Code approve. After approval, Claude updates `docs/BUILD_PLAN.md` (and bumps its version and change log) or the contracts, regenerating code in the same PR.

## Template

```markdown
## CR-xxx: <short title>
- Raised by: <agent or human>, <date and time IST>, while working on T-xxx
- Problem: <what in the plan or contract is wrong or missing>
- Proposal: <the exact change>
- Affected sections: <BUILD_PLAN sections>   Affected tasks: <T-xxx>
- Decision: approved | rejected | deferred, by <who>, <date>
- Done in: PR #<n>, plan version <x.y>
```

## Open

## CR-001: Host the API and worker without Google billing
- Raised by: claude, 2026-11-26, while setting up T-000 accounts
- Problem: BUILD_PLAN 8, 9.2 and 30.2 put the API and worker on Cloud Run. The Cloud Run Admin API cannot be enabled on the Parampara Google project because it has no billing account, and the human will not enable billing (D-011).
- Proposal: host the FastAPI API and the job worker as one Docker container on a no-card free host. Render free web service from the GitHub repo (sleeps after 15 minutes idle, so a warm-up ping is needed before the demo). Hugging Face Docker Spaces were checked on 2026-11-26 and are marked Paid on the human's account, so they are out. Replace `make deploy-api` and T-017 AC1 accordingly. Web stays on Vercel. Secrets go in the host's secret store instead of Secret Manager.
- Affected sections: 8, 9.1, 9.2, 30.2, 30.4   Affected tasks: T-017, T-049
- Decision: approved (Render free web service), by human delegation to claude, 2026-11-26. Plan text updated in v1.1. The Render service is created when T-017 adds the Dockerfile.
- Done in: -

## CR-003: give_hint level parameter must not use an integer enum
- Raised by: claude, 2026-11-26, while reviewing T-016 (docs/audits/2026-11-26-gemini-batch-1-review.md)
- Problem: 16.5 declares `"level": {"type": "integer", "enum": [1, 2, 3]}`. The Gemini schema only allows string enums; the SDK rejects the declaration, so the coach would get no tools.
- Proposal: `"level": {"type": "integer", "minimum": 1, "maximum": 3}`. Checked against the live API on 2026-11-26.
- Affected sections: 16.5   Affected tasks: T-016, T-015
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (T-016 token tools)

## CR-004: fresh Live token for reconnect
- Raised by: claude, 2026-11-26, from T-003 findings
- Problem: tokens are single use (verified: a second connect fails with "Token has been used too many times"), so 16.6's reconnect with a resumption handle has no token to use.
- Proposal: `POST /v1/sessions/{id}/live-token` with `{resumption_handle}` returns a new single-use token whose locked config carries that handle. Trainee of that session only, rate limit 6 per minute.
- Affected sections: 12.2, 16.2, 16.6   Affected tasks: T-016, T-015
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (route), Claude (T-015 client)

## CR-005: assurance, coach and edge_fps in the session summary
- Raised by: gemini (spec gap 1), confirmed by claude, 2026-11-26
- Problem: 16.7, 17.4, 18.1 and 18.3 require `assurance`, `coach: scripted` and `edge_fps` in the summary, but `session-summary.schema.json` has no such fields and forbids extra ones.
- Proposal: add `assurance: "two_key" | "single" | "manual"` to `StepOutcome`; add `coach: "live" | "scripted"` and `edge_fps: number | null` to `SessionSummary`. Regenerate contracts.
- Affected sections: 10.3, 18, 19   Affected tasks: T-020, T-030, T-037
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: contracts done; Gemini fills the fields (T-016, T-020, T-030)

## CR-006: draft skill version for the interviewer
- Raised by: gemini (spec gap 2), confirmed by claude, 2026-11-26
- Problem: 15 runs the interview on a draft through `/skill-versions/{id}`, but 14.2 only creates a `skill_versions` row at `finalize`.
- Proposal: when a compile run reaches `awaiting_review`, create a `skill_versions` row with status `draft` holding the draft graph; `finalize` approves that row instead of inserting a new one.
- Affected sections: 12.2, 14.2, 15   Affected tasks: T-021, T-028
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (T-021, T-028)

## CR-007: idempotency_keys table
- Raised by: gemini (spec gap 3), confirmed by claude, 2026-11-26
- Problem: 12.1 requires stored Idempotency-Key values for money and ledger writes; 11.1 has nowhere to store them. T-010 added an `idempotency_keys` table not in the plan.
- Proposal: keep the table in 11.1, add `request_sha256 text not null` so a reused key with a different body returns 409, and purge rows older than 24 hours.
- Affected sections: 11.1, 12.1   Affected tasks: T-010, T-034, T-042
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (T-010 migration, T-034, T-042)

## CR-008: verifier falls back from MODEL_FLASH to MODEL_LITE inside one 8 s deadline
- Raised by: claude, 2026-11-26, while verifying Gemini batch 2
- Problem: 13.1 routes `verify` to `MODEL_FLASH`. On the free tier (D-011), measured 2026-11-26: one real verify through the API timed out at 8 s (10.4 s wall); in a run of 9 calls `gemini-3.5-flash` returned 503 "high demand" on all 9; `gemini-3.5-flash-lite` answered 3 of 3 in 1.5 to 3.7 s with a valid verdict. With flash alone the VLM key almost never arrives, so no step can complete.
- Proposal: `verify` tries `MODEL_FLASH` first; on 429, 503 or no answer by 4 s it calls `MODEL_LITE` with the remaining budget; one overall deadline of 8 s; `VerifierVerdict.model` records the model that answered. The eval report (29.3) reports accuracy per model.
- Affected sections: 13.1, 18.3   Affected tasks: T-020, T-047
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (T-020 verifier)

## CR-009: every step needs at least one edge check
- Raised by: claude, 2026-11-26, while verifying Gemini batch 2
- Problem: 10.2 only requires edge checks on critical steps, but the two-key rule (18.1) means a step with no edge check can never complete, and completing it on the VLM key alone breaks the rule that no LLM output alone completes a step.
- Proposal: `skill_lint` reports `step_without_edge_check` for any step with an empty `edge_checks`; the predicate writer prompt already adds `hands_settled` in that case (14.4 task 2). The terminal-wiring fixture already complies.
- Affected sections: 10.2, 14.6   Affected tasks: T-022, T-021
- Decision: approved by the human, 2026-11-26
- Done in: plan v1.1 (claude); code: Gemini (T-022 skill_lint)

## CR-010: generated OpenAPI types live outside the contracts drift folder
- Raised by: claude, 2026-11-26, while doing T-012
- Problem: the typed API client needs types generated from the API's OpenAPI document. They are generated output, but `scripts/gen_contracts.sh --check` diffs all of `packages/contracts/src/generated/` and `scripts/size_check.py` only skips listed generated paths, so the 1,000-line file fails one gate or the other.
- Proposal: generate them into `packages/contracts/src/openapi/paths.d.ts` (`pnpm --filter @parampara/web gen:api`) and add that folder to the size check's and eslint's generated-path lists. No threshold changes.
- Affected sections: 7, 31.8   Affected tasks: T-012
- Decision: pending human (done on the T-012 branch so the gate passes; revert if rejected)
- Done in: T-012 PR

## Closed

(none yet)
