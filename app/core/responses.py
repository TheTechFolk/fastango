# app/core/responses.py
from typing import Any

from pydantic import BaseModel

from app.core.constants import ERROR_MSG, SUCCESS_MSG


class APIResponse[T](BaseModel):
    """Standard API response envelope used across all endpoints."""

    error: bool = False
    message: str = SUCCESS_MSG
    data: T | None = None


def success_response(data: Any = None, message: str = SUCCESS_MSG) -> dict:
    """Build a standard success response dictionary."""
    return {"error": False, "message": message, "data": data}


def error_response(message: str = ERROR_MSG, data: Any = None) -> dict:
    """Build a standard error response dictionary."""
    return {"error": True, "message": message, "data": data}
