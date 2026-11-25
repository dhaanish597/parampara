# Handoffs

One file per task: `docs/handoffs/T-xxx.md`, written by the task owner at the end of every session. It is the shared memory between agents, so the next agent never starts cold. Keep it short and factual.

## Template

```markdown
# T-xxx: <title>
Agent: claude | codex | gemini        Date: <YYYY-MM-DD HH:MM IST>
Branch: agent/<agent>/T-xxx-<slug>    PR: #<n>

## What I built
- ...

## Acceptance criteria
- [x] AC1 ... (test: path::test_name, or manual check: what and where the evidence is)
- [ ] AC2 ... (why not yet)

## Contracts used or touched
- <schema file> (read only)

## Decisions I made (proposals for DECISIONS.md)
- ...

## Open questions or spec gaps
- ...

## Next agent should know
- ...

## Checks
- make check: pass | fail
- make test-e2e: pass | fail | not run
- Manual: devices and steps tried
```
