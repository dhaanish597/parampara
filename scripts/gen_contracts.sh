#!/usr/bin/env bash
# Regenerate TS and Pydantic types from contracts/schemas. `--check` fails if output is stale.
set -euo pipefail
cd "$(dirname "$0")/.."

TS_OUT="packages/contracts/src/generated"
PY_OUT="services/api/src/parampara/domain/generated.py"
PY="uv run --project services/api python"

generate() { # $1 = ts dir, $2 = python file
  local bundle
  bundle="$(mktemp -d)/contracts.json" # fixed name: the generator writes it into the header
  $PY scripts/bundle_contracts.py > "$bundle"
  node scripts/gen_ts_contracts.mjs "$bundle" "$1"
  uv run --project services/api datamodel-codegen --input "$bundle" --input-file-type jsonschema \
    --output "$2" --output-model-type pydantic_v2.BaseModel --target-python-version 3.12 \
    --use-annotated --disable-timestamp --use-title-as-name --formatters ruff-format ruff-check \
    2>/dev/null
}

if [[ "${1:-}" == "--check" ]]; then
  tmp="$(mktemp -d "$PWD/services/api/.gen-check.XXXXXX")"
  trap 'rm -rf "$tmp"' EXIT
  generate "$tmp/ts" "$tmp/generated.py"
  if ! diff -r "$tmp/ts" "$TS_OUT" >/dev/null || ! diff "$tmp/generated.py" "$PY_OUT" >/dev/null; then
    echo "contract drift: run 'make contracts' and commit the result"
    exit 1
  fi
else
  generate "$TS_OUT" "$PY_OUT"
fi
$PY scripts/validate_fixtures.py
