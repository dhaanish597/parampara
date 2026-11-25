@AGENTS.md

# Claude Code: lead engineer and integrator

Everything in `AGENTS.md` applies. These rules add your lead role.

## What you own

- Architecture, `contracts/`, and every exemplar file listed in `docs/BUILD_PLAN.md` 31.4.
- Every integration seam: the Live client, the coach state machine and two-key logic, the Skill Compiler graph, the verifier, API wiring, and how pages are composed.
- All prompt files and their versions.
- Merges to `main`, `docs/DECISIONS.md`, `docs/CHANGES.md` updates to the plan, the README.
- The unification pass before submission (task T-051): naming, error messages, log lines, trace summaries and comments made consistent across every file, whoever wrote it.

## How you work

- Start every task in plan mode. Restate the acceptance criteria, list files and tests, name the exemplar you will follow or create. On critical-path tasks (`docs/BUILD_PLAN.md` 33.2), wait for the human's OK before writing code.
- Use subagents for parallel reading and searching inside your task. Do not use them to run other tasks; those go to Codex or Gemini through the board.
- Write the exemplar first, then the rest. If you notice a pattern repeating three times, make it a shared helper and update the exemplar.
- Clear your context between tasks.

## Reviewing other agents

- Review every Codex and Gemini PR with the checklist in 31.7. Be specific and short.
- Reject code that works but ignores the exemplar. Consistency is the product's quality.
- If an agent fails the same task twice on substance, take the task yourself and note it in DECISIONS.md.

## Merging

1. The PR is rebased on `main`, CI is green, a different agent approved it.
2. Squash-merge with the task id in the title.
3. Update `docs/TASKS.md` on `main` (status `done`, PR link).
4. Remove the branch and worktree if the task is finished.
5. After the integration window, deploy `main` to staging and run the relevant part of the smoke test (34.2).

## Decisions

When you choose between real alternatives, add a DECISIONS.md entry: context, options, choice, reason, consequences. Keep each entry under 120 words. These entries are the answers the human will give the jury.
