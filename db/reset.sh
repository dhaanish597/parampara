#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PATH="/opt/homebrew/bin:/usr/local/bin:$HOME/.local/bin:$PATH"

if [[ -n "${DATABASE_URL:-}" ]]; then
  DB_URL="$DATABASE_URL"
elif pg_isready -h 127.0.0.1 -p 54322 -U postgres >/dev/null 2>&1; then
  DB_URL="postgresql://postgres:postgres@127.0.0.1:54322/postgres"
else
  DB_NAME="${PARAMPARA_LOCAL_DB:-parampara_dev}"
  DB_USER="${PGUSER:-$(whoami)}"
  psql -h 127.0.0.1 -p 5432 -U "$DB_USER" -d postgres -tc \
    "SELECT 1 FROM pg_database WHERE datname = '${DB_NAME}'" | grep -q 1 || \
    createdb -h 127.0.0.1 -p 5432 -U "$DB_USER" "$DB_NAME"
  DB_URL="postgresql://${DB_USER}@127.0.0.1:5432/${DB_NAME}"
fi

echo "Resetting database: ${DB_URL}"

IS_SUPABASE="$(psql "$DB_URL" -tAc "SELECT count(*) FROM pg_tables WHERE schemaname = 'auth' AND tablename = 'users'")"

if [[ "$IS_SUPABASE" == "0" ]]; then
  # Plain Postgres: emulate the small Supabase surface the migrations need.
  # Real Supabase already has these roles, auth.users and auth.uid(); never replace them.
  psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'anon') THEN
    CREATE ROLE anon NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'authenticated') THEN
    CREATE ROLE authenticated NOLOGIN NOINHERIT;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'service_role') THEN
    CREATE ROLE service_role NOLOGIN NOINHERIT BYPASSRLS;
  END IF;
END $$;
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (id uuid PRIMARY KEY, email text);
CREATE OR REPLACE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT coalesce(
    nullif(current_setting('request.jwt.claim.sub', true), ''),
    nullif(current_setting('request.jwt.claims', true), '')::jsonb ->> 'sub'
  )::uuid
$$;
SQL
fi

psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
DROP SCHEMA IF EXISTS public CASCADE;
CREATE SCHEMA public;
GRANT USAGE ON SCHEMA public TO anon, authenticated, service_role;
GRANT ALL ON SCHEMA public TO postgres, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO anon, authenticated, service_role;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO anon, authenticated, service_role;
SQL

HAS_VECTOR="$(psql "$DB_URL" -tAc "SELECT count(*) FROM pg_available_extensions WHERE name = 'vector'")"
if [[ "$HAS_VECTOR" == "0" ]]; then
  echo "Note: pgvector not installed in local Postgres; installing local vector(n) domain shim."
  psql "$DB_URL" -v ON_ERROR_STOP=1 <<'SQL'
CREATE DOMAIN public.vector AS real[];
SQL
fi

for migration in "$ROOT_DIR"/db/migrations/*.sql; do
  echo "Applying $(basename "$migration")..."
  if [[ "$HAS_VECTOR" == "0" ]]; then
    sed 's/^create extension if not exists vector;/-- vector extension shimmed locally/' "$migration" \
      | sed 's/vector(768)/public.vector/g' \
      | psql "$DB_URL" -v ON_ERROR_STOP=1
  else
    psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$migration"
  fi
done

echo "Running minimal seed..."
DATABASE_URL="$DB_URL" uv run --project "$ROOT_DIR/services/api" python "$ROOT_DIR/db/seed/seed.py"
echo "db-reset complete."
