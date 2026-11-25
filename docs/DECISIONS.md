# DECISIONS.md: why Parampara is built this way

Maintained by Claude Code. Other agents propose decisions in their handoffs. Each entry: context, options, choice, reason, consequences, under 120 words. These are the answers to the jury's "why did you do it this way?" questions.

---

## D-001 Claude Code leads; Codex and Gemini build inside its patterns
- **Context:** three coding agents, five days, one codebase that must read as one author.
- **Options:** equal peers; one lead with specialists; one tool only.
- **Choice:** Claude Code leads architecture, contracts, exemplars, integration and merges. Codex builds bounded test-first modules. Gemini verifies Google APIs, tunes prompts on video, labels evals and audits.
- **Reason:** in our experience Claude-built code is more coherent; parallel lanes are still needed for speed.
- **Consequences:** Claude is on the critical path; exemplars and the unification pass keep style consistent.

## D-002 The two-key rule for step completion
- **Context:** an LLM that says "done" when it isn't would make credentials worthless.
- **Options:** VLM only; deterministic only; both.
- **Choice:** a step completes only when the on-device edge check and a VLM verdict both pass within 5 s.
- **Reason:** deterministic checks are fast and explainable but narrow; the VLM generalises but can be wrong. Together they are hard to fool.
- **Consequences:** steps with no deterministic check are marked single assurance and shown as such.

## D-003 Pre-error interrupts run on the device, not in the cloud
- **Context:** the Live model sees about one frame per second and replies in about a second or more.
- **Choice:** MediaPipe and colour rules in the browser fire "Ruko" within 300 ms and then tell the coach.
- **Reason:** safety warnings cannot wait for a network round trip.
- **Consequences:** parts are recognised by calibrated colour, so the demo skill uses clearly different wire colours.

## D-004 Contract-first with generated types
- **Context:** three agents coding in parallel against shared data.
- **Choice:** JSON Schemas in `contracts/` generate TypeScript and Pydantic types; a drift check fails CI.
- **Reason:** removes a whole class of integration bugs between lanes.
- **Consequences:** contract changes go through a Change Request.

## D-005 Gemini Live with context compression and resumption
- **Context:** audio and video Live sessions end after about 2 minutes without compression; a connection lasts about 10 minutes.
- **Choice:** sliding-window compression, session resumption handles, 1 fps frames only while coaching, scripted fallback.
- **Consequences:** T-003 verifies settings on the day.

## D-006 Bayesian Knowledge Tracing with fixed parameters
- **Context:** need an explainable mastery estimate per step from a handful of runs.
- **Choice:** classic BKT with P_L0 0.2, P_T 0.15, P_S 0.10, P_G 0.20.
- **Reason:** simple, well understood, easy to explain; no training data needed.
- **Consequences:** parameters are tuned after the pilot, not before.

## D-007 Credentials as W3C VCs with eddsa-jcs-2022 and did:web
- **Choice:** JSON canonicalisation (JCS) instead of RDF canonicalisation; Ed25519; issuer as did:web on our domain.
- **Reason:** standard, verifiable in the browser, no blockchain cost, simple to implement correctly.
- **Consequences:** the production domain is fixed before the first credential.

## D-008 Hash-chained consent ledger in Postgres, not a blockchain
- **Choice:** append-only table with SHA-256 chain and a locked head row.
- **Reason:** tamper-evident, cheap, easy to verify and explain; ready to plug into a registered DPDP consent manager later.

## D-009 Royalty split 25 / 10 / 65 with a worker pool of 50 / 40 / 10
- **Choice:** platform 25%, factory 10%, workers 65%; within workers, master 50%, trainees 40% by episodes, reviewer 10%; parent master gets 25% of the master share on lineage.
- **Reason:** workers get the majority; simple enough to explain on stage. Revisit in the pilot.

## D-010 Payouts in test mode, simulated fallback
- **Choice:** RazorpayX test mode when available, otherwise a clearly labelled simulated provider.
- **Reason:** no real money during judging; account activation may not be possible in time.

## D-011 Gemini free tier only
- **Context:** the human will not enable Google billing.
- **Options:** pay for Live quotas; free tier only.
- **Choice:** free tier only, with a scripted fallback and cached results where quotas bite.
- **Reason:** no spend during the build; limits are measured in T-003.
- **Consequences:** demo must be rehearsed inside quotas; eval and usage runs are batched and small.

