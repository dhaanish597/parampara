.PHONY: setup contracts db-reset dev check test-e2e eval usage deploy-api lint-py lint-ts

API_DIR := services/api
PY := uv run --project $(API_DIR) python

setup:
	pnpm install
	cd $(API_DIR) && uv sync
	@echo "Playwright browsers install in T-012 once the web app exists."

contracts:
	@bash scripts/gen_contracts.sh

db-reset:
	@bash db/reset.sh

dev:
	@echo "dev arrives with T-011 and T-012"; exit 1

lint-py:
	cd $(API_DIR) && uv run ruff check . && uv run ruff format --check . && uv run mypy

lint-ts:
	pnpm lint && pnpm typecheck

check: lint-py lint-ts
	cd $(API_DIR) && uv run pytest -q
	pnpm test
	@bash scripts/gen_contracts.sh --check
	$(PY) scripts/size_check.py
	$(PY) scripts/banned_terms.py
	gitleaks detect --no-banner --redact --source . --no-git=false

test-e2e:
	@echo "test-e2e arrives with T-012"; exit 1

eval:
	@echo "eval arrives with T-047"; exit 1

usage:
	@echo "usage arrives with T-047"; exit 1

deploy-api:
	@echo "deploy-api arrives with T-017"; exit 1
