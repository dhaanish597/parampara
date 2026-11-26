"""Background job worker loop (BUILD_PLAN 12.3, T-023).

Polls Postgres `jobs` every 1 second using `FOR UPDATE SKIP LOCKED`, runs at
most 2 jobs concurrently, retries up to 3 times with backoff (5 s, 30 s, 120 s),
and records `last_error` and trace events on failure.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from parampara.api.settings import Settings, get_settings
from parampara.db.jobs import (
    MAX_ATTEMPTS,
    JobRecord,
    claim_next_job,
    complete_job,
    fail_job,
)
from parampara.db.pool import close_pool, init_pool, resolve_database_url
from parampara.domain.generated import Kind4, Scope4
from parampara.telemetry.recorder import get_telemetry_bus
from parampara.worker_jobs.finalize_clip import handle_finalize_clip

logger = logging.getLogger(__name__)

JobHandler = Callable[[dict[str, Any], Settings], Awaitable[dict[str, Any]]]


def default_handlers() -> dict[str, JobHandler]:
    """Return the registered background job handlers."""
    return {
        "finalize_clip": handle_finalize_clip,
    }


class WorkerRunner:
    """Async job worker with bounded concurrency and retry backoff."""

    def __init__(
        self,
        settings: Settings,
        handlers: dict[str, JobHandler] | None = None,
        *,
        max_concurrency: int = 2,
        poll_interval_s: float = 1.0,
        max_attempts: int = MAX_ATTEMPTS,
    ) -> None:
        self.settings = settings
        self.handlers = handlers if handlers is not None else default_handlers()
        self.max_concurrency = max(1, max_concurrency)
        self.poll_interval_s = poll_interval_s
        self.max_attempts = max_attempts
        self._sem = asyncio.Semaphore(self.max_concurrency)
        self._tasks: set[asyncio.Task[None]] = set()

    async def execute_job(self, job: JobRecord) -> str:
        """Execute a single claimed job and update its terminal or retry state."""
        db_url = resolve_database_url(self.settings.database_url)
        handler = self.handlers.get(job.kind)
        if handler is None:
            msg = f"Unknown job kind: {job.kind}"
            return await fail_job(
                db_url, job.id, attempts=job.attempts, error=msg, max_attempts=self.max_attempts
            )
        try:
            await handler(job.payload, self.settings)
            await complete_job(db_url, job.id)
            return "done"
        except Exception as exc:
            err = f"{type(exc).__name__}: {exc}"
            logger.warning("Job %s (%s) attempt %d failed: %s", job.id, job.kind, job.attempts, err)
            get_telemetry_bus().record_trace(
                agent="worker",
                kind=Kind4.error,
                summary=f"Job {job.kind} failed (attempt {job.attempts}): {err[:120]}",
                scope=Scope4(),
            )
            return await fail_job(
                db_url, job.id, attempts=job.attempts, error=err, max_attempts=self.max_attempts
            )

    async def _run_with_semaphore(self, job: JobRecord) -> None:
        try:
            await self.execute_job(job)
        finally:
            self._sem.release()

    async def poll_once(self, *, kinds: list[str] | None = None) -> int:
        """Claim up to available concurrency slots and dispatch jobs concurrently."""
        db_url = resolve_database_url(self.settings.database_url)
        if not db_url:
            return 0
        dispatched = 0
        while not self._sem.locked():
            await self._sem.acquire()
            job = await claim_next_job(db_url, kinds=kinds)
            if job is None:
                self._sem.release()
                break
            task = asyncio.create_task(self._run_with_semaphore(job))
            self._tasks.add(task)
            task.add_done_callback(self._tasks.discard)
            dispatched += 1
        return dispatched

    async def drain(self) -> None:
        """Wait for all currently running worker tasks to finish."""
        if self._tasks:
            await asyncio.gather(*list(self._tasks), return_exceptions=True)

    async def run_forever(self, stop_event: asyncio.Event | None = None) -> None:
        """Poll for jobs until stop_event is set."""
        stopper = stop_event or asyncio.Event()
        while not stopper.is_set():
            try:
                dispatched = await self.poll_once()
            except Exception as exc:
                logger.warning("Worker poll error: %s", exc)
                dispatched = 0
            if dispatched == 0:
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stopper.wait(), timeout=self.poll_interval_s)
        await self.drain()


async def _main() -> None:
    settings = get_settings()
    await init_pool(settings.database_url)
    try:
        runner = WorkerRunner(settings)
        await runner.run_forever()
    finally:
        await close_pool()


if __name__ == "__main__":
    asyncio.run(_main())
