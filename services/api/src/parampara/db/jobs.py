"""PostgreSQL-backed background jobs queue (BUILD_PLAN 12.3, T-023)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.db.pool import open_db

MAX_ATTEMPTS = 3
BACKOFF_SECONDS: tuple[int, ...] = (5, 30, 120)


@dataclass(frozen=True)
class JobRecord:
    id: UUID
    kind: str
    payload: dict[str, Any]
    status: str
    attempts: int
    last_error: str | None
    run_after: datetime
    created_at: datetime
    updated_at: datetime


def _row_to_job(row: dict[str, Any]) -> JobRecord:
    return JobRecord(
        id=UUID(str(row["id"])),
        kind=str(row["kind"]),
        payload=dict(row["payload"]),
        status=str(row["status"]),
        attempts=int(row["attempts"]),
        last_error=str(row["last_error"]) if row["last_error"] is not None else None,
        run_after=row["run_after"],
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


def backoff_seconds_for_attempt(attempt: int) -> int:
    """Return exponential retry delay (5s, 30s, 120s) for 1-indexed attempt."""
    idx = max(0, min(attempt - 1, len(BACKOFF_SECONDS) - 1))
    return BACKOFF_SECONDS[idx]


async def enqueue_job(database_url: str, *, kind: str, payload: dict[str, Any]) -> UUID:
    """Insert a new queued job row and return its UUID."""
    job_id = uuid4()
    sql = (
        "INSERT INTO jobs (id, kind, payload, status) "
        "VALUES (%s, %s, %s::jsonb, 'queued') RETURNING id"
    )
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(sql, (job_id, kind, json.dumps(payload)))
    return job_id


_CLAIM_ALL_SQL = (
    "WITH next_job AS ("
    "  SELECT id FROM jobs WHERE status = 'queued' AND run_after <= now() "
    "  ORDER BY run_after ASC, created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1"
    ") UPDATE jobs j SET status = 'running', attempts = j.attempts + 1, updated_at = now() "
    "FROM next_job WHERE j.id = next_job.id "
    "RETURNING j.id, j.kind, j.payload, j.status::text AS status, "
    "j.attempts, j.last_error, j.run_after, j.created_at, j.updated_at"
)
_CLAIM_KINDS_SQL = (
    "WITH next_job AS ("
    "  SELECT id FROM jobs WHERE status = 'queued' AND run_after <= now() AND kind = ANY(%s) "
    "  ORDER BY run_after ASC, created_at ASC FOR UPDATE SKIP LOCKED LIMIT 1"
    ") UPDATE jobs j SET status = 'running', attempts = j.attempts + 1, updated_at = now() "
    "FROM next_job WHERE j.id = next_job.id "
    "RETURNING j.id, j.kind, j.payload, j.status::text AS status, "
    "j.attempts, j.last_error, j.run_after, j.created_at, j.updated_at"
)


async def claim_next_job(database_url: str, *, kinds: list[str] | None = None) -> JobRecord | None:
    """Atomically claim one due queued job via FOR UPDATE SKIP LOCKED."""
    sql = _CLAIM_KINDS_SQL if kinds else _CLAIM_ALL_SQL
    params: tuple[Any, ...] = (kinds,) if kinds else ()
    async with open_db(database_url) as conn, conn.transaction():
        row = await (await conn.execute(sql, params)).fetchone()
    return _row_to_job(dict(row)) if row else None


async def complete_job(database_url: str, job_id: UUID) -> None:
    """Mark a running job as done."""
    sql = "UPDATE jobs SET status = 'done', last_error = NULL, updated_at = now() WHERE id = %s"
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(sql, (job_id,))


async def fail_job(
    database_url: str,
    job_id: UUID,
    *,
    attempts: int,
    error: str,
    max_attempts: int = MAX_ATTEMPTS,
) -> str:
    """Record last_error and either requeue with backoff or mark permanently failed."""
    err_msg = error[:2000]
    if attempts < max_attempts:
        delay = backoff_seconds_for_attempt(attempts)
        sql = (
            "UPDATE jobs SET status = 'queued', last_error = %s, "
            "run_after = now() + (%s * interval '1 second'), updated_at = now() "
            "WHERE id = %s"
        )
        async with open_db(database_url) as conn, conn.transaction():
            await conn.execute(sql, (err_msg, delay, job_id))
        return "queued"
    sql = "UPDATE jobs SET status = 'failed', last_error = %s, updated_at = now() WHERE id = %s"
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(sql, (err_msg, job_id))
    return "failed"


async def get_job(database_url: str, job_id: UUID) -> JobRecord | None:
    """Fetch a job row by ID."""
    sql = (
        "SELECT id, kind, payload, status::text AS status, attempts, last_error, "
        "run_after, created_at, updated_at FROM jobs WHERE id = %s"
    )
    async with open_db(database_url) as conn:
        row = await (await conn.execute(sql, (job_id,))).fetchone()
    return _row_to_job(dict(row)) if row else None
