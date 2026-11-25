# Pinned Stack & Package Versions (T-003)

**Checked:** 2026-11-26 IST
Reference: `docs/BUILD_PLAN.md` Section 8.

## 1. Runtime & Tooling

| Tool | Pinned / Verified Version |
| --- | --- |
| Node.js | `26.13.0` local (`engines: >=22`) |
| pnpm | `12.14.0` (`packageManager` in root) |
| Python | `3.12.16` (managed by `uv`) |
| uv | `0.13.10` |
| ffmpeg | Installed via Homebrew (`/opt/homebrew/bin/ffmpeg`) |
| gitleaks | Installed via Homebrew (`/opt/homebrew/bin/gitleaks`) |

## 2. Python Backend (`services/api/uv.lock`)

| Package | Pinned Version | Notes |
| --- | --- | --- |
| `fastapi` | `0.165.0` | REST API |
| `uvicorn` | `0.54.0` | ASGI server |
| `pydantic` | `2.14.4` | Data validation / generated contracts |
| `pydantic-settings` | `2.16.3` | Env config (`settings.py`) |
| `psycopg` / `psycopg-binary` | `3.3.9` | Async Postgres 3 driver |
| `psycopg-pool` | `3.3.3` | Connection pool |
| `google-genai` | `3.6.1` | Gemini API, Live ephemeral tokens (`v1alpha`), TTS (`v1beta`) |
| `pynacl` | `1.6.2` | Ed25519 VC signing |
| `rfc8785` | `0.1.4` | JCS canonicalisation |
| `base58` | `2.1.1` | Multikey & proofValue encoding |
| `httpx` | `0.28.1` | Async HTTP client & FastAPI test client |
| `python-dotenv` | `1.2.4` | Local `.env` loading |
| `jinja2` | `3.1.6` | Refinery data card template |
| `pytest` | `9.2.0` | Unit & API tests |
| `pytest-asyncio` | `1.5.0` | Async tests |
| `pytest-cov` | `7.1.0` | Coverage checks |
| `ruff` | `0.17.6` | Linter & formatter |
| `mypy` | `2.4.1` | Static type checking |
| `datamodel-code-generator` | `0.102.0` | JSON Schema -> Pydantic codegen |
| `jsonschema` | `4.26.0` | Contract fixture validation |
| `langgraph` / `langgraph-checkpoint-postgres` | To be pinned in T-021 | Skill Compiler graph |
| `langfuse` | To be pinned in T-011 | LLM observability |
| `mediapipe` / `lerobot` | To be pinned in T-040 | Offline refinery & LeRobotDataset v3.0 |

## 3. Web & Workspace (`pnpm-lock.yaml`)

| Package | Pinned Version | Notes |
| --- | --- | --- |
| `typescript` | `5.9.3` | Strict TS |
| `eslint` | `9.39.5` | Linter |
| `typescript-eslint` | `8.74.0` | TS lint rules |
| `vitest` | `3.2.7` | Unit tests |
| `json-schema-to-typescript` | `16.0.0` | JSON Schema -> TS codegen |
| `next` / `react` / `tailwindcss` | To be pinned in T-012 | Next.js App Router PWA |
| `@google/genai` | `1.30.0` (verified in spike) | Browser Live API client (pin in T-015) |
| `@mediapipe/tasks-vision` | To be pinned in T-014 | Browser HandLandmarker & FaceDetector |
| `@noble/ed25519`, `canonicalize`, `bs58`, `qrcode.react` | To be pinned in T-033 | In-browser VC verification & QR |
| `recharts` | To be pinned in T-045 | Dashboard charts |
| `@playwright/test` | To be pinned in T-012 | E2E with fake camera |

## 4. Verified Gemini Model IDs (`services/api/.env`)

- `MODEL_LIVE=gemini-3.8-live`
- `MODEL_FLASH=gemini-3.5-flash`
- `MODEL_LITE=gemini-3.5-flash-lite`
- `MODEL_TTS=gemini-3.8-flash-lite-tts`
