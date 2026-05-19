"""Shared API error response helpers."""

from http import HTTPStatus
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException


class ErrorBody(BaseModel):
    """Stable error body returned by API exception handlers."""

    code: str
    message: str
    request_id: str
    details: dict[str, Any] | list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    """Top-level error response model."""

    error: ErrorBody = Field(..., description="Machine-readable API error payload.")


def _request_id(request: Request) -> str:
    return str(getattr(request.state, "request_id", "unknown"))


def _status_code_name(status_code: int) -> str:
    try:
        return HTTPStatus(status_code).phrase.lower().replace(" ", "_")
    except ValueError:
        return "http_error"


def build_error_response(
    request: Request,
    *,
    status_code: int,
    code: str,
    message: str,
    details: dict[str, Any] | list[dict[str, Any]] | None = None,
) -> JSONResponse:
    """Build the repository-wide API error envelope."""

    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(
            error=ErrorBody(
                code=code,
                message=message,
                request_id=_request_id(request),
                details=details,
            )
        ).model_dump(),
    )


async def http_exception_handler(request: Request, exc: HTTPException) -> JSONResponse:
    message = str(exc.detail) if exc.detail else _status_code_name(exc.status_code)
    return build_error_response(
        request,
        status_code=exc.status_code,
        code=_status_code_name(exc.status_code),
        message=message,
    )


async def validation_exception_handler(
    request: Request,
    exc: RequestValidationError,
) -> JSONResponse:
    return build_error_response(
        request,
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code="validation_error",
        message="Request validation failed.",
        details=exc.errors(),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return build_error_response(
        request,
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        code="internal_server_error",
        message="Internal server error.",
    )


def install_exception_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(Exception, unhandled_exception_handler)
