"""SSE agent trace stream endpoint (BUILD_PLAN 12.2 & 26)."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from parampara.api.deps import CurrentUser, get_current_user, require_role
from parampara.api.errors import AppError
from parampara.api.settings import Settings, get_settings
from parampara.db.pool import open_db, resolve_database_url
from parampara.db.repos.telemetry import fetch_recent_traces_db
from parampara.domain.generated import TraceEvent
from parampara.telemetry.recorder import get_telemetry_bus

router = APIRouter(prefix="/v1")


class RecentTracesResponse(BaseModel):
    items: list[TraceEvent]


async def _check_trace_access(
    user: CurrentUser, session_id: UUID | None, database_url: str
) -> None:
    if not user.memberships:
        raise AppError(status_code=403, code="forbidden", message="Org membership required")
    if session_id is None:
        return
    url = resolve_database_url(database_url)
    if not url:
        return
    async with open_db(url) as conn:
        row = await (
            await conn.execute(
                "SELECT org_id, trainee_user_id FROM sessions WHERE id = %s", (session_id,)
            )
        ).fetchone()
    if row is None:
        return
    if UUID(str(row["trainee_user_id"])) != user.user_id:
        require_role(user, UUID(str(row["org_id"])), {"owner", "supervisor"})


@router.get("/traces/recent", response_model=RecentTracesResponse)
async def recent_traces(
    session_id: Annotated[UUID | None, Query()] = None,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> RecentTracesResponse:
    await _check_trace_access(user, session_id, settings.database_url)
    url = resolve_database_url(settings.database_url)
    if url:
        db_items = await fetch_recent_traces_db(url, session_id=session_id)
        if db_items:
            return RecentTracesResponse(items=db_items)
    return RecentTracesResponse(items=get_telemetry_bus().recent_traces(session_id=session_id))


@router.get("/traces/stream")
async def stream_traces(
    session_id: Annotated[UUID | None, Query()] = None,
    compile_run_id: Annotated[UUID | None, Query()] = None,
    max_events: Annotated[int | None, Query(ge=1, le=500)] = None,
    user: CurrentUser = Depends(get_current_user),  # noqa: B008
    settings: Settings = Depends(get_settings),  # noqa: B008
) -> StreamingResponse:
    await _check_trace_access(user, session_id, settings.database_url)
    bus = get_telemetry_bus()

    async def event_gen() -> AsyncIterator[str]:
        sent = 0
        async for ev in bus.subscribe(session_id=session_id, compile_run_id=compile_run_id):
            data = ev.model_dump_json(exclude_none=True)
            yield f"id: {ev.id}\nevent: trace\ndata: {data}\n\n"
            sent += 1
            if max_events is not None and sent >= max_events:
                break
            await asyncio.sleep(0)

    return StreamingResponse(event_gen(), media_type="text/event-stream")
