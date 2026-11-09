# app/exceptions.py
"""
Fastango — Centralized Exception Handlers

Every error leaves the app in the same {error, message, data} envelope that
success responses use. Without these handlers FastAPI emits four different
shapes: the envelope for 500s, {"detail": "..."} for HTTPException,
{"detail": [...]} for validation errors, and a 500 for every AppException.

The rate-limit 429 is wired here too, for the same reason — slowapi's stock
handler returns its own shape, so a client parsing `message`/`data` breaks on
that one status alone.
"""

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from sqlalchemy.exc import IntegrityError, OperationalError, SQLAlchemyError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.config import settings
from app.core.constants import (
    ALREADY_EXISTS_MSG,
    CONFLICT_MSG,
    ERROR_MSG,
    RATE_LIMITED_MSG,
    SERVICE_UNAVAILABLE_MSG,
    VALIDATION_ERROR_MSG,
)
from app.core.exceptions import AppException
from app.core.responses import error_response

logger = logging.getLogger("fastango")


def _field_errors(exc: RequestValidationError) -> dict[str, str]:
    """Flatten pydantic errors to {field: message}, in every environment.

    A frontend needs to know which field failed. Only pydantic's `msg` goes
    out — never `input`, which would echo back whatever was sent, passwords
    included.
    """
    return {
        ".".join(str(part) for part in err["loc"][1:]) or "body": err["msg"] for err in exc.errors()
    }


def _is_unique_violation(exc: IntegrityError) -> bool:
    """True for a duplicate key, as opposed to a foreign-key or NOT NULL failure.

    Postgres says so with SQLSTATE 23505; SQLite only in the message text.
    """
    orig = exc.orig
    return getattr(orig, "sqlstate", None) == "23505" or "UNIQUE constraint failed" in str(orig)


def _envelope(
    status_code: int, message: str, headers: dict[str, str] | None = None, **kwargs
) -> JSONResponse:
    """One envelope builder, so every handler emits the same shape.

    X-Request-ID is added by request_id_middleware on the way out.
    """
    return JSONResponse(
        status_code=status_code,
        content=error_response(message=message, **kwargs),
        headers=headers,
    )


def configure_exceptions(app: FastAPI) -> None:
    """Mount all centralized exception handlers onto the FastAPI application."""

    @app.exception_handler(AppException)
    async def app_exception_handler(request: Request, exc: AppException):
        """One handler for the whole AppException family.

        Status and message both come off the instance, so adding a new
        exception type never requires touching this function.
        """
        return _envelope(exc.status_code, exc.message)

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        """Request body/query validation failures."""
        return _envelope(422, VALIDATION_ERROR_MSG, data=_field_errors(exc))

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        """429 in the app's envelope, with the retry hint clients need."""
        return _envelope(
            429,
            RATE_LIMITED_MSG,
            headers={"Retry-After": str(getattr(exc, "retry_after", 60) or 60)},
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        """A constraint violation is the caller's problem, not a server fault.

        Without this every unique/FK violation outside the one place that
        catches it by hand becomes an opaque 500.
        """
        logger.warning("Integrity error on %s %s", request.method, request.url.path)
        # Only a duplicate key means "already exists". A foreign-key failure is
        # the opposite — something referenced does not exist — so it gets the
        # neutral message rather than a wrong one.
        return _envelope(409, ALREADY_EXISTS_MSG if _is_unique_violation(exc) else CONFLICT_MSG)

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        """The database is unreachable or timed out — 503, not 500."""
        logger.error("Database unavailable on %s %s", request.method, request.url.path)
        return _envelope(503, SERVICE_UNAVAILABLE_MSG, headers={"Retry-After": "5"})

    @app.exception_handler(SQLAlchemyError)
    async def sqlalchemy_error_handler(request: Request, exc: SQLAlchemyError):
        """Anything else from the driver layer, still in the envelope."""
        logger.exception("Database error on %s %s", request.method, request.url.path)
        message = f"{ERROR_MSG} ({exc})" if settings.is_dev else ERROR_MSG
        return _envelope(500, message)

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(request: Request, exc: StarletteHTTPException):
        """Anything the framework itself raises — unknown routes, bad methods."""
        # Re-attach headers or 401s lose their WWW-Authenticate challenge.
        return _envelope(exc.status_code, str(exc.detail), headers=dict(exc.headers or {}))

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all for genuinely unexpected failures. Registered last."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        message = f"{ERROR_MSG} ({exc})" if settings.is_dev else ERROR_MSG
        return _envelope(500, message)
