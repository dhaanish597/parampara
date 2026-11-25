"""Structured API errors using the generated ApiError contract (BUILD_PLAN 12.1)."""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from parampara.domain.generated import ApiError, Error


class AppError(Exception):
    def __init__(
        self,
        *,
        status_code: int,
        code: str,
        message: str,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _err(
    request: Request,
    status: int,
    code: str,
    message: str,
    details: dict[str, Any] | None = None,
) -> JSONResponse:
    req_id = getattr(request.state, "request_id", None) or str(uuid4())
    payload = ApiError(error=Error(code=code, message=message, details=details, request_id=req_id))
    body = payload.model_dump(mode="json", exclude_none=True)
    return JSONResponse(status_code=status, content=body)


async def _handle_app(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, AppError)  # noqa: S101
    return _err(request, exc.status_code, exc.code, exc.message, exc.details)


async def _handle_validation(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, RequestValidationError)  # noqa: S101
    return _err(
        request, 422, "validation_error", "Request validation failed", {"errors": exc.errors()}
    )


async def _handle_http(request: Request, exc: Exception) -> JSONResponse:
    assert isinstance(exc, StarletteHTTPException)  # noqa: S101
    return _err(request, exc.status_code, f"http_{exc.status_code}", str(exc.detail))


async def _handle_unexpected(request: Request, _exc: Exception) -> JSONResponse:
    return _err(request, 500, "internal_error", "Internal server error")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, _handle_app)
    app.add_exception_handler(RequestValidationError, _handle_validation)
    app.add_exception_handler(StarletteHTTPException, _handle_http)
    app.add_exception_handler(Exception, _handle_unexpected)
