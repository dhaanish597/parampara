"""FastAPI application entrypoint (BUILD_PLAN 12.1)."""

from __future__ import annotations

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from parampara.api.errors import register_error_handlers
from parampara.api.routes import (
    auth,
    consents,
    health,
    licences,
    live_token,
    sessions,
    skill_versions,
    traces,
)
from parampara.api.settings import get_settings
from parampara.db.pool import close_pool, init_pool
from parampara.telemetry.recorder import get_telemetry_bus


@asynccontextmanager
async def _lifespan(_app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    await init_pool(settings.database_url)
    get_telemetry_bus().configure(
        database_url=settings.database_url,
        langfuse_public_key=settings.langfuse_public_key,
        langfuse_secret_key=settings.langfuse_secret_key,
        langfuse_host=settings.langfuse_host,
    )
    try:
        yield
    finally:
        await get_telemetry_bus().flush()
        await close_pool()


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(title="Parampara API", version=settings.app_version, lifespan=_lifespan)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[settings.public_web_origin],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def attach_request_id(
        request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        req_id = request.headers.get("X-Request-Id") or str(uuid4())
        request.state.request_id = req_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = req_id
        return response

    register_error_handlers(app)
    app.include_router(health.router)
    app.include_router(auth.router)
    app.include_router(skill_versions.router)
    app.include_router(traces.router)
    app.include_router(consents.router)
    app.include_router(licences.router)
    app.include_router(sessions.router)
    app.include_router(live_token.router)
    return app


app = create_app()
