"""Telemetry recorder for trace_events (SSE + Postgres) and model_calls (BUILD_PLAN 13.3)."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import AsyncIterator, Coroutine
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from parampara.db.pool import resolve_database_url
from parampara.db.repos.telemetry import insert_model_call_db, insert_trace_event_db
from parampara.domain.generated import Kind4, Scope4, TraceEvent
from parampara.telemetry.langfuse_sink import emit_langfuse_generation

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class ModelCallRecord:
    agent: str
    model: str
    purpose: str
    input_tokens: int | None
    output_tokens: int | None
    latency_ms: int
    cost_usd: float
    ok: bool
    error: str | None = None
    session_id: UUID | None = None
    compile_run_id: UUID | None = None
    dataset_id: UUID | None = None
    langfuse_trace_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))


class TelemetryBus:
    """In-process trace event bus + call ledger that mirrors writes to Postgres and Langfuse."""

    def __init__(self) -> None:
        self._seq = 0
        self._events: list[TraceEvent] = []
        self._calls: list[ModelCallRecord] = []
        self._subscribers: list[asyncio.Queue[TraceEvent]] = []
        self._database_url: str = ""
        self._langfuse_public_key: str = ""
        self._langfuse_secret_key: str = ""
        self._langfuse_host: str = "https://cloud.langfuse.com"
        self._pending_tasks: set[asyncio.Task[Any]] = set()

    def configure(
        self,
        *,
        database_url: str = "",
        langfuse_public_key: str = "",
        langfuse_secret_key: str = "",
        langfuse_host: str = "https://cloud.langfuse.com",
    ) -> None:
        self._database_url = resolve_database_url(database_url)
        self._langfuse_public_key = langfuse_public_key
        self._langfuse_secret_key = langfuse_secret_key
        self._langfuse_host = langfuse_host

    def _spawn(self, coro: Coroutine[Any, Any, Any]) -> None:
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            coro.close()
            return
        task = loop.create_task(self._safe_run(coro))
        self._pending_tasks.add(task)
        task.add_done_callback(self._pending_tasks.discard)

    async def _safe_run(self, coro: Coroutine[Any, Any, Any]) -> None:
        try:
            await coro
        except Exception as exc:
            logger.debug("Telemetry mirror failed: %s", exc)

    async def flush(self) -> None:
        if self._pending_tasks:
            await asyncio.gather(*list(self._pending_tasks), return_exceptions=True)

    def record_trace(
        self,
        *,
        agent: str,
        kind: Kind4,
        summary: str,
        scope: Scope4,
        model: str | None = None,
        latency_ms: int | None = None,
    ) -> TraceEvent:
        self._seq += 1
        event = TraceEvent(
            id=self._seq,
            scope=scope,
            agent=agent,
            kind=kind,
            summary=summary,
            model=model,
            latency_ms=latency_ms,
            created_at=datetime.now(UTC),
        )
        self._events.append(event)
        for q in list(self._subscribers):
            q.put_nowait(event)
        if self._database_url:
            self._spawn(insert_trace_event_db(self._database_url, event))
        return event

    def _call_params(self, r: ModelCallRecord, trace_id: str | None) -> tuple[Any, ...]:
        return (
            r.agent,
            r.model,
            r.purpose,
            r.input_tokens,
            r.output_tokens,
            r.latency_ms,
            r.cost_usd,
            r.ok,
            r.error,
            r.session_id,
            r.compile_run_id,
            r.dataset_id,
            trace_id,
        )

    def record_model_call(self, r: ModelCallRecord) -> None:
        has_lf = bool(self._langfuse_public_key and self._langfuse_secret_key)
        trace_id = r.langfuse_trace_id or (str(uuid4()) if has_lf else None)
        self._calls.append(r)
        if self._database_url:
            self._spawn(
                insert_model_call_db(
                    self._database_url, self._call_params(r, trace_id), r.created_at
                )
            )
        if trace_id and has_lf:
            meta = {
                "agent": r.agent,
                "model": r.model,
                "purpose": r.purpose,
                "input_tokens": r.input_tokens,
                "output_tokens": r.output_tokens,
                "latency_ms": r.latency_ms,
                "ok": r.ok,
                "error": r.error,
            }
            self._spawn(
                emit_langfuse_generation(
                    public_key=self._langfuse_public_key,
                    secret_key=self._langfuse_secret_key,
                    host=self._langfuse_host,
                    trace_id=trace_id,
                    meta=meta,
                )
            )

    def recent_traces(self, *, session_id: UUID | None = None) -> list[TraceEvent]:
        if session_id is None:
            return list(self._events[-100:])
        return [e for e in self._events if e.scope.session_id == session_id]

    def usage_summary(self) -> list[dict[str, Any]]:
        grouped: dict[tuple[str, str], dict[str, Any]] = {}
        for c in self._calls:
            bucket = grouped.setdefault(
                (c.agent, c.model),
                {
                    "agent": c.agent,
                    "model": c.model,
                    "calls": 0,
                    "input_tokens": 0,
                    "output_tokens": 0,
                    "cost_usd": 0.0,
                    "latencies_ms": [],
                },
            )
            bucket["calls"] += 1
            bucket["input_tokens"] += c.input_tokens or 0
            bucket["output_tokens"] += c.output_tokens or 0
            bucket["cost_usd"] += c.cost_usd
            bucket["latencies_ms"].append(c.latency_ms)
        return list(grouped.values())

    async def subscribe(
        self,
        *,
        session_id: UUID | None = None,
        compile_run_id: UUID | None = None,
    ) -> AsyncIterator[TraceEvent]:
        queue: asyncio.Queue[TraceEvent] = asyncio.Queue()
        self._subscribers.append(queue)
        try:
            while True:
                ev = await queue.get()
                if session_id and ev.scope.session_id != session_id:
                    continue
                if compile_run_id and ev.scope.compile_run_id != compile_run_id:
                    continue
                yield ev
        finally:
            self._subscribers.remove(queue)


_DEFAULT_BUS = TelemetryBus()


def get_telemetry_bus() -> TelemetryBus:
    return _DEFAULT_BUS
