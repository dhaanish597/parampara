# AGENTS.md: shared rules for every coding agent on Parampara

Claude Code, Codex and Gemini all read this file. It is the one rulebook. Tool-specific additions live in `CLAUDE.md` and `GEMINI.md` and never contradict this file.

## What we are building

Parampara turns one master worker's demonstration into a live Hindi AI coach, a verifiable Proof-of-Skill credential, and robot-training data the workers own and earn royalties on. Entry for BUILD 2036 (TiE Global Summit 2026), Frontier 04.

## Sources of truth, in order of precedence

1. `contracts/schemas/` for data shapes. Never hand-edit generated code (`packages/contracts/`, `services/api/src/parampara/domain/generated.py`). Run `make contracts`.
2. `docs/BUILD_PLAN.md` for behaviour, scope, architecture and task cards. Read only the sections your task card lists.
3. This file for how we work.
4. `docs/DECISIONS.md` for why. It never overrides the plan.

If the plan is silent or wrong, stop and write the question in your handoff (`docs/handoffs/T-xxx.md`). Do not guess. Do not work around the spec.

## The team

| Member | Role |
| --- | --- |
| Claude Code | Lead engineer and integrator. Owns architecture, contracts, exemplars, integration, prompts, merges. |
| Codex | Module builder and second reviewer. Builds bounded, test-first modules inside the exemplar patterns. |
| Gemini | Researcher, multimodal specialist and auditor. Verifies Google APIs, tunes prompts on real video, drafts eval labels, Hindi copy, whole-repo audits. |
| Human (Dhaanish) | Product owner and dispatcher. Owns the board, approves merges, tests on phones. |

We work as one engineer with three pairs of hands. Code must read as if one careful person wrote it.

## Every session

**Start**
1. Read this file and your tool file (`CLAUDE.md` or `GEMINI.md`).
2. Read your task card in `docs/BUILD_PLAN.md` section 32 and only the sections it lists.
3. Read the handoffs of the task's dependencies in `docs/handoffs/`.
4. Restate the acceptance criteria and list the files you will touch before writing code.

**End**
1. `make check` passes.
2. Write or update `docs/handoffs/T-xxx.md` using the template in `docs/handoffs/README.md`.
3. Commit with trailers, push, open or update the PR.
4. One task per session. Then stop.

## Commands

| Command | Use |
| --- | --- |
| `make setup` | Install everything |
| `make contracts` | Regenerate types from `contracts/schemas` |
| `make db-reset` | Fresh local database with migrations and seed |
| `make dev` | Run web, API and worker |
| `make check` | The quality gate. Must pass before any PR |
| `make test-e2e` | Playwright with a fake camera |
| `make eval` | Eval harness, writes `evals/EVAL_REPORT.md` |
| `make usage` | Writes `docs/USAGE.md` from real model calls |

## Repository map

- `apps/web`: Next.js PWA. `lib/edge` (on-device vision), `lib/live` (Gemini Live client), `lib/coach` (state machine, two-key logic), `lib/vc` (credential verification), `lib/i18n`.
- `services/api/src/parampara`: FastAPI `api/`, LLM `agents/`, deterministic `tools/`, `db/`, `telemetry/`, `worker.py`, `worker_jobs/`.
- `contracts/`: schemas and fixtures. `db/`: migrations and seed. `evals/`: harness and labels. `docs/`: plan, board, decisions, handoffs.

## Coding rules

**General**
- Follow the exemplar for the kind of file you write (list in `docs/BUILD_PLAN.md` 31.4). Copy its structure, naming, error handling, logging and tests.
- Files at most 300 lines. Functions at most 40 lines. Split instead of growing.
- No dead code. No `TODO` without a task id (`TODO(T-045): ...`).
- No model ids outside `services/api/src/parampara/api/settings.py` and `apps/web/lib/live/config.ts`.
- No demo ids, names or magic values in core code. Seed data lives in `db/seed/`.
- Every user-facing string goes through i18n (`hi.json`, `en.json`). Hindi is mandatory for anything a worker sees or hears.
- Money is integer paise. Timestamps are ISO 8601 UTC. Image coordinates are normalised 0 to 1.

**Python**
- Python 3.12, uv, ruff, mypy (strict in `tools/` and `agents/`), pytest.
- Pydantic v2 models from `domain/generated.py`. Plain SQL in `db/repos/`; no ORM.
- Every model call goes through `agents/llm.py`. Never import `google.genai` elsewhere except the Live token minting module.
- Deterministic tools in `tools/` are pure functions with exhaustive tests. They never call an LLM.

**TypeScript**
- Strict mode, eslint, vitest. Use generated contract types from `packages/contracts`.
- Pure logic (edge features and rules, two-key logic, VC verification) never imports browser APIs, so it can be unit tested.

**Agents and prompts**
- One prompt file per agent in `agents/prompts/`, with headings Role, Inputs, Task, Rules, Refuse or escalate when, Output, and a `prompt_version` line.
- Prompt text from the plan is copied verbatim on first write. Later edits need a reviewer and a version bump.
- Every agent action writes a `trace_events` row with a one-line summary written for a judge.

## Product and safety rules (never break these)

- No face recognition, no biometric identification, no per-worker productivity, speed, idle-time or ranking features. `scripts/banned_terms.py` enforces this.
- Faces are blurred on the device before any recording leaves the phone.
- No LLM output alone completes a step, issues a credential, writes consent or moves money. Deterministic tools and the two-key rule decide.
- Every use of a clip beyond the worker's own coaching needs an effective consent scope, checked at export and again at licence time.
- Payouts run in test mode only, and the UI says so.
- Secrets live only in env and Secret Manager. The browser never sees the Gemini API key; it uses single-use ephemeral tokens.
- Training benches are never powered. The coach refuses live electrical advice.

## Git

- Work in your own worktree: `../pp-claude`, `../pp-codex`, `../pp-gemini`.
- Branch: `agent/<claude|codex|gemini>/T-xxx-<slug>`. One task per branch.
- Conventional Commits with trailers:

```text
feat(edge): add wrong_part_near_zone rule with cooldown

Implements BUILD_PLAN 17.4.

Task: T-013
Agent: codex
```

- PR title `T-xxx: <title>`. PR body is your handoff. About 400 changed lines at most, excluding generated files and fixtures.
- Rebase on `main` before review. Only Claude Code (or the human on its recommendation) merges, by squash, after a different agent approves and CI is green.
- Never edit `docs/TASKS.md` in a branch. The human or Claude updates it on `main`.

## Reviews

Use the checklist in `docs/BUILD_PLAN.md` 31.7. Answer `APPROVE` or `CHANGES`, then a numbered list of `path:line, problem, fix`. Do not rewrite the author's code.

## The quality gate

`make check` runs ruff, mypy, pytest, eslint, tsc, vitest, the contract drift check, the size check, the banned-terms check and gitleaks. Never disable a check, add a blanket ignore or lower a threshold. Changing the gate is a Change Request (`docs/CHANGES.md`).

## When stuck

- Spec gap or contradiction: stop, write the question in your handoff, tell the human.
- External API behaves differently from the plan: Gemini verifies and records it in `docs/research/`, then a Change Request updates the plan.
- Two agents disagree: Claude decides and records it in `docs/DECISIONS.md`.
- A flaky test: fix it or quarantine it with a task id the same day. Never delete a test to pass.
