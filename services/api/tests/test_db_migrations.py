"""Tests for SQL migrations, RLS policies, and dashboard views (BUILD_PLAN 11, T-010)."""

from __future__ import annotations

import os
import re
from pathlib import Path

import psycopg
import pytest

MIGRATIONS = Path(__file__).resolve().parents[3] / "db" / "migrations"


def _local_db_url() -> str | None:
    candidates = [
        os.environ.get("DATABASE_URL"),
        "postgresql://postgres:postgres@127.0.0.1:54322/postgres",
        f"postgresql://{os.environ.get('USER', 'dhaanish')}@127.0.0.1:5432/parampara_dev",
    ]
    for url in candidates:
        if not url:
            continue
        try:
            with psycopg.connect(url, connect_timeout=1) as conn:
                conn.execute("SELECT 1")
            return url
        except psycopg.Error:
            continue
    return None


def test_migration_files_exist_in_order() -> None:
    for name in ("0001_init.sql", "0002_rls.sql", "0003_views.sql"):
        assert (MIGRATIONS / name).exists(), f"Missing {name}"


def test_rls_enabled_on_every_table_and_consent_append_only() -> None:
    init_sql = (MIGRATIONS / "0001_init.sql").read_text(encoding="utf-8")
    rls_sql = (MIGRATIONS / "0002_rls.sql").read_text(encoding="utf-8")
    tables = set(re.findall(r"create table (\w+)", init_sql))
    rls_tables = set(re.findall(r"alter table (\w+) enable row level security", rls_sql))
    assert tables == rls_tables, f"Tables missing RLS: {tables - rls_tables}"
    assert "trainee_user_id = auth.uid()" in rls_sql
    assert "before update or delete on public.consent_records" in rls_sql
    assert "before truncate on public.consent_records" in rls_sql
    assert "set search_path" in rls_sql.lower()


def test_views_exist_with_security_invoker_and_revoked_from_clients() -> None:
    views_sql = (MIGRATIONS / "0003_views.sql").read_text(encoding="utf-8")
    for view_name in ("v_skill_matrix", "v_time_to_competency", "v_step_hotspots", "v_earnings"):
        assert f"create or replace view {view_name}" in views_sql
    assert views_sql.lower().count("security_invoker = true") == 4
    assert "revoke all on" in views_sql.lower()


def test_live_postgres_p0_5_and_p0_6_enforcement() -> None:
    db_url = _local_db_url()
    if db_url is None:
        pytest.skip("Local PostgreSQL is not reachable")
    with psycopg.connect(db_url, autocommit=False) as conn:
        with pytest.raises(psycopg.errors.InsufficientPrivilege), conn.transaction():
            conn.execute("SET LOCAL ROLE anon")
            conn.execute("SELECT * FROM v_earnings")
        with (
            pytest.raises((psycopg.errors.InsufficientPrivilege, psycopg.errors.RaiseException)),
            conn.transaction(),
        ):
            conn.execute("SET LOCAL ROLE authenticated")
            conn.execute("TRUNCATE consent_records CASCADE")
        with pytest.raises(psycopg.errors.RaiseException), conn.transaction():
            conn.execute("TRUNCATE consent_records CASCADE")


def test_live_postgres_search_path_and_skill_matrix_guard() -> None:
    db_url = _local_db_url()
    if db_url is None:
        pytest.skip("Local PostgreSQL is not reachable")
    with psycopg.connect(db_url, autocommit=False) as conn:
        row = conn.execute("SELECT proconfig FROM pg_proc WHERE proname = 'is_member'").fetchone()
        assert row is not None and row[0] is not None
        assert any(str(item).startswith("search_path=") for item in row[0])
        with conn.transaction():
            conn.execute(
                "INSERT INTO mastery (user_id, skill_version_id, step_id, p_learned, observations) "
                "VALUES ('20000000-0000-4000-8000-000000000003', "
                "'30000000-0000-4000-8000-000000000002', 's1', 0.95, 3) ON CONFLICT DO NOTHING"
            )
            status = conn.execute(
                "SELECT status FROM v_skill_matrix "
                "WHERE user_id = '20000000-0000-4000-8000-000000000003' "
                "AND skill_version_id = '30000000-0000-4000-8000-000000000002'"
            ).fetchone()
            assert status is not None and status[0] != "exam_ready"
            raise psycopg.Rollback()
