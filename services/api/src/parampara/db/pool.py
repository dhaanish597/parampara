"""Async PostgreSQL connection pool for Parampara API and worker (BUILD_PLAN 11)."""

from __future__ import annotations

import asyncio
import os
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import psycopg
from psycopg.rows import dict_row
from psycopg_pool import AsyncConnectionPool

_POOL: AsyncConnectionPool[Any] | None = None
_POOL_URL: str = ""
_POOL_LOOP_ID: int | None = None


def resolve_database_url(database_url: str | None = None) -> str:
    """Return configured database URL or empty string if unconfigured."""
    if database_url and database_url.strip():
        return database_url.strip()
    return os.environ.get("DATABASE_URL", "").strip()


async def init_pool(database_url: str | None = None) -> AsyncConnectionPool[Any] | None:
    """Open the process-wide AsyncConnectionPool at FastAPI startup."""
    global _POOL, _POOL_URL, _POOL_LOOP_ID
    url = resolve_database_url(database_url)
    if not url:
        return None
    loop_id = id(asyncio.get_running_loop())
    if _POOL is not None and url == _POOL_URL and loop_id == _POOL_LOOP_ID:
        return _POOL
    await close_pool()
    pool: AsyncConnectionPool[Any] = AsyncConnectionPool(
        conninfo=url,
        min_size=1,
        max_size=10,
        kwargs={"row_factory": dict_row},
        open=False,
    )
    await pool.open()
    _POOL = pool
    _POOL_URL = url
    _POOL_LOOP_ID = loop_id
    return pool


async def close_pool() -> None:
    """Close the active AsyncConnectionPool on application shutdown."""
    global _POOL, _POOL_URL, _POOL_LOOP_ID
    if _POOL is not None:
        pool = _POOL
        _POOL = None
        _POOL_URL = ""
        _POOL_LOOP_ID = None
        await pool.close()


def pool_is_open() -> bool:
    """Return True when the shared AsyncConnectionPool is initialized."""
    return _POOL is not None


@asynccontextmanager
async def open_db(database_url: str | None = None) -> AsyncIterator[psycopg.AsyncConnection[Any]]:
    """Borrow a pooled async psycopg connection (or open a short-lived one in unit tests)."""
    url = resolve_database_url(database_url)
    if not url:
        raise RuntimeError("DATABASE_URL is not configured")
    loop_id = id(asyncio.get_running_loop())
    if _POOL is not None and url == _POOL_URL and loop_id == _POOL_LOOP_ID:
        async with _POOL.connection() as conn:
            yield conn
        return
    conn = await psycopg.AsyncConnection.connect(url, row_factory=dict_row)
    try:
        yield conn
    finally:
        await conn.close()
