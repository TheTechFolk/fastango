# app/exceptions.py
"""
Fastango — Centralized Exception Handlers

Consolidates all global error handling and exception trapping into a single layer,
keeping the app initialization in main.py clean and focused.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.config import settings

logger = logging.getLogger("fastango")


def configure_exceptions(app: FastAPI) -> None:
    """Mount all centralized exception handlers onto the FastAPI application."""

    @app.exception_handler(Exception)
    async def global_exception_handler(request: Request, exc: Exception):
        """Catch-all handler that wraps unhandled exceptions in the standard response envelope."""
        logger.exception("Unhandled exception on %s %s", request.method, request.url.path)
        
        # Show detailed exception details only in non-production environments
        if settings.APP_ENV in ("local", "test", "testing"):
            error_msg = f"Internal server error: {str(exc)}"
        else:
            error_msg = "Internal server error."

        return JSONResponse(
            status_code=500,
            content={
                "error": True,
                "message": error_msg,
                "data": None,
            },
        )

