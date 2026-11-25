# Parampara

One master worker's demonstration becomes a live Hindi AI coach, a verifiable Proof-of-Skill credential, and robot-training data the workers own and earn royalties on. BUILD 2036, Frontier 04.

Start here: `AGENTS.md` (rules), `docs/BUILD_PLAN.md` (spec), `docs/TASKS.md` (board), `docs/GEMINI_START.md` (first session for Gemini).

## Quick start

```bash
make setup      # pnpm install + uv sync
make contracts  # regenerate types from contracts/schemas
make check      # the quality gate
```

Requires Node 22+, pnpm, uv (Python 3.12 is fetched by uv), gitleaks. Secrets: copy `services/api/.env.example` to `services/api/.env` and fill it in. Real values are never committed.
