"""PostgreSQL repository for trace_events and model_calls (BUILD_PLAN 11.1 & 13.3)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from parampara.db.pool import open_db
from parampara.domain.generated import Kind4, Scope4, TraceEvent


async def insert_trace_event_db(database_url: str, event: TraceEvent) -> None:
    """Persist a TraceEvent row into public.trace_events."""
    sql = (
        "INSERT INTO trace_events "
        "(session_id, compile_run_id, dataset_id, agent, kind, summary, "
        "model, latency_ms, payload, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s::jsonb, %s)"
    )
    params = (
        event.scope.session_id,
        event.scope.compile_run_id,
        event.scope.dataset_id,
        event.agent,
        event.kind.value,
        event.summary,
        event.model,
        event.latency_ms,
        json.dumps({}),
        event.created_at,
    )
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(sql, params)


async def insert_model_call_db(
    database_url: str, params: tuple[Any, ...], created_at: datetime
) -> None:
    """Persist a ModelCallRecord row into public.model_calls."""
    sql = (
        "INSERT INTO model_calls "
        "(agent, model, purpose, input_tokens, output_tokens, latency_ms, cost_usd, "
        "ok, error, session_id, compile_run_id, dataset_id, langfuse_trace_id, created_at) "
        "VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"
    )
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(sql, (*params, created_at))


def _row_to_trace(r: dict[str, Any]) -> TraceEvent:
    return TraceEvent(
        id=int(r["id"]),
        scope=Scope4(
            session_id=r["session_id"],
            compile_run_id=r["compile_run_id"],
            dataset_id=r["dataset_id"],
        ),
        agent=str(r["agent"]),
        kind=Kind4(str(r["kind"])),
        summary=str(r["summary"]),
        model=r["model"],
        latency_ms=r["latency_ms"],
        created_at=r["created_at"],
    )


async def fetch_recent_traces_db(
    database_url: str, *, session_id: UUID | None = None, limit: int = 100
) -> list[TraceEvent]:
    """Load recent trace_events rows from PostgreSQL."""
    by_session = (
        "SELECT id, session_id, compile_run_id, dataset_id, agent, kind, summary, "
        "model, latency_ms, created_at FROM trace_events "
        "WHERE session_id = %s ORDER BY id ASC LIMIT %s"
    )
    all_recent = (
        "SELECT id, session_id, compile_run_id, dataset_id, agent, kind, summary, "
        "model, latency_ms, created_at FROM trace_events ORDER BY id DESC LIMIT %s"
    )
    async with open_db(database_url) as conn:
        if session_id is not None:
            cur = await conn.execute(by_session, (session_id, limit))
        else:
            cur = await conn.execute(all_recent, (limit,))
        rows = await cur.fetchall()
    return [_row_to_trace(dict(r)) for r in rows]


async def fetch_usage_summary_db(database_url: str) -> list[dict[str, Any]]:
    """Aggregate model_calls by agent and model from PostgreSQL."""
    sql = (
        "SELECT agent, model, count(*)::int AS calls, "
        "coalesce(sum(input_tokens), 0)::int AS input_tokens, "
        "coalesce(sum(output_tokens), 0)::int AS output_tokens, "
        "coalesce(sum(cost_usd), 0)::float AS cost_usd, "
        "coalesce(array_agg(latency_ms ORDER BY id), ARRAY[]::int[]) AS latencies_ms "
        "FROM model_calls GROUP BY agent, model ORDER BY agent, model"
    )
    async with open_db(database_url) as conn:
        cur = await conn.execute(sql)
        return [dict(r) for r in await cur.fetchall()]
