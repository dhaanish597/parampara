"""Idempotency-Key persistence and 409 conflict checking (BUILD_PLAN 12.1 & CR-007)."""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from parampara.api.errors import AppError
from parampara.db.pool import open_db
from parampara.tools.hashing import sha256_canonical_json


def hash_request_body(payload: dict[str, Any]) -> str:
    return sha256_canonical_json(payload)


async def check_idempotency(
    database_url: str,
    *,
    key: str,
    route: str,
    user_id: UUID,
    request_sha256: str,
) -> dict[str, Any] | None:
    """Return cached JSON response on replay, or raise 409 if body hash differs (CR-007)."""
    if not database_url or not key:
        return None
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(
            "DELETE FROM idempotency_keys WHERE created_at < now() - interval '24 hours'"
        )
        row = await (
            await conn.execute(
                "SELECT request_sha256, response FROM idempotency_keys "
                "WHERE key = %s AND route = %s AND user_id = %s",
                (key, route, user_id),
            )
        ).fetchone()
    if row is None:
        return None
    if str(row["request_sha256"]) != request_sha256:
        raise AppError(
            status_code=409,
            code="idempotency_conflict",
            message="Idempotency-Key reused with a different request body",
        )
    return dict(row["response"])


async def store_idempotency(
    database_url: str,
    *,
    key: str,
    route: str,
    user_id: UUID,
    request_sha256: str,
    response_body: dict[str, Any],
) -> None:
    if not database_url or not key:
        return
    async with open_db(database_url) as conn, conn.transaction():
        await conn.execute(
            "INSERT INTO idempotency_keys (key, route, user_id, request_sha256, response) "
            "VALUES (%s, %s, %s, %s, %s::jsonb) ON CONFLICT (key, route, user_id) DO NOTHING",
            (key, route, user_id, request_sha256, json.dumps(response_body)),
        )
