# app/core/responses.py
from typing import Any

from pydantic import BaseModel

from app.core.constants import ERROR_MSG, SUCCESS_MSG


class APIResponse[T](BaseModel):
    """Standard API response envelope used across all endpoints."""

    error: bool = False
    message: str = SUCCESS_MSG
    data: T | None = None


class ErrorResponse(BaseModel):
    """The same envelope on failure — what every handler in app/exceptions.py emits.

    Declared so the OpenAPI schema describes the errors clients actually get.
    Left alone, FastAPI documents its own {"detail": [...]} shape for 422 and
    nothing at all for 401/404, and a generated client is wrong on every error.
    """

    error: bool = True
    message: str
    # Only a 422 fills this in: {field: what is wrong with it}.
    data: dict[str, str] | None = None


def error_responses(*status_codes: int) -> dict[int | str, dict[str, Any]]:
    """`responses=` for a router or route: these statuses return ErrorResponse.

    @router.get("/{code}", response_model=..., responses=error_responses(404))
    """
    return {code: {"model": ErrorResponse} for code in status_codes}


def success_response(data: Any = None, message: str = SUCCESS_MSG) -> dict:
    """Build a standard success response dictionary."""
    return {"error": False, "message": message, "data": data}


def error_response(message: str = ERROR_MSG, data: Any = None) -> dict:
    """Build a standard error response dictionary."""
    return {"error": True, "message": message, "data": data}
