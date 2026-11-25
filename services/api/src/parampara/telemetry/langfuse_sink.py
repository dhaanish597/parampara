"""Optional non-blocking Langfuse span emitter (BUILD_PLAN 13.3, T-011 AC3)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import uuid4

import httpx

logger = logging.getLogger(__name__)


def _build_batch(trace_id: str, meta: dict[str, Any]) -> dict[str, Any]:
    now = datetime.now(UTC).isoformat().replace("+00:00", "Z")
    return {
        "batch": [
            {
                "id": str(uuid4()),
                "type": "generation-create",
                "timestamp": now,
                "body": {
                    "id": str(uuid4()),
                    "traceId": trace_id,
                    "name": f"{meta['agent']}:{meta['purpose']}",
                    "model": meta["model"],
                    "startTime": now,
                    "endTime": now,
                    "usage": {
                        "input": meta["input_tokens"] or 0,
                        "output": meta["output_tokens"] or 0,
                    },
                    "metadata": {
                        "latency_ms": meta["latency_ms"],
                        "ok": meta["ok"],
                        "error": meta["error"],
                    },
                },
            }
        ]
    }


async def emit_langfuse_generation(
    *,
    public_key: str,
    secret_key: str,
    host: str,
    trace_id: str,
    meta: dict[str, Any],
) -> None:
    """Send a lightweight generation span to Langfuse when keys are configured."""
    if not public_key or not secret_key:
        return
    url = f"{host.rstrip('/')}/api/public/ingestion"
    try:
        async with httpx.AsyncClient(timeout=3.0) as client:
            await client.post(url, json=_build_batch(trace_id, meta), auth=(public_key, secret_key))
    except Exception as exc:
        logger.debug("Langfuse span delivery skipped: %s", exc)
