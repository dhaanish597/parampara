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
- Decision: approved (Render free web service), by human delegation to claude, 2026-11-26. Plan text update pending. The Render service is created when T-017 adds the Dockerfile.
- Done in: -

## Closed

(none yet)
