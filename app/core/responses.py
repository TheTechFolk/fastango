# app/core/responses.py
from typing import Any, Generic, TypeVar

from pydantic import BaseModel

T = TypeVar("T")


class APIResponse(BaseModel, Generic[T]):
    """Standard API response envelope used across all endpoints."""

    error: bool = False
    message: str = "Request executed successfully"
    data: T | None = None


def success_response(
    data: Any = None,
    message: str = "Request executed successfully",
) -> dict:
    """
    Build a standard success response dictionary.

    Args:
        data: The payload to return to the client.
        message: A human-readable status message.

    Returns:
        A dictionary conforming to APIResponse schema.
    """
    return {
        "error": False,
        "message": message,
        "data": data,
    }


def error_response(
    message: str = "An error occurred",
    data: Any = None,
) -> dict:
    """
    Build a standard error response dictionary.

    Args:
        message: A human-readable error description.
        data: Optional error detail payload.

    Returns:
        A dictionary conforming to APIResponse schema.
    """
    return {
        "error": True,
        "message": message,
        "data": data,
    }
