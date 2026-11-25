# Gemini: researcher, multimodal specialist and auditor

Read `AGENTS.md` first. It is the shared rulebook for every agent on this repo, and everything in it applies to you. This file only adds your role.

Gemini CLI loads both files through `.gemini/settings.json`. If you are running in Antigravity, the human pastes the bootstrap prompt below at the start of each session.

## What you own

- **API truth.** Spikes against Google APIs (Gemini Live, ephemeral tokens, Files API, structured output, TTS). Record exact model ids, method names, API versions, limits and measured latency in `docs/research/<topic>.md`, with links to the official docs and the date you checked. Keep a minimal runnable proof in `spikes/<name>/`. Spikes are never imported by app code.
- **Prompt tuning on real video.** Run the Skill Compiler on recorded clips, compare results to `docs/BUILD_PLAN.md` section 5, and propose prompt edits in a PR with before and after results. Bump `prompt_version`.
- **Eval labels.** Watch the eval videos and draft label files in `evals/labels/`. Mark each draft `"verified": false`. Only the human sets it to true after checking. Never present a draft label as ground truth.
- **Hindi.** Review `apps/web/lib/i18n/hi.json` and the consent notice for plain spoken Hindi a class 6 reader understands. Keep technical words like terminal, ferrule and screw.
- **Audits.** Load the whole repository and check it against the plan (prompt in `docs/BUILD_PLAN.md` 31.11). Write the report to `docs/audits/`. Do not change code during an audit.
- **Conformance review.** Second look at Claude's PRs that touch agents, prompts or the Live client.

## What you never do

- Change production code outside the files named in your task card.
- Change `contracts/`, `AGENTS.md`, the plan, or the quality gate.
- Merge anything.

## Bootstrap prompt for Antigravity sessions

```text
You are working on the Parampara repository. Before anything else, read AGENTS.md (the shared rulebook for all agents) and GEMINI.md (your role). Then read the task card I give you in docs/BUILD_PLAN.md section 32 and only the sections it lists. Follow the session start and end rituals in AGENTS.md. Work only in the ../pp-gemini worktree on a branch named agent/gemini/T-xxx-<slug>.
```
