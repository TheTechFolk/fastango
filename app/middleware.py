# app/middleware.py
"""
Fastango — Centralized Middleware Configurations

Wires up global application middlewares (TrustedHost, CORS, security headers,
audit/timing logging). Middlewares are added innermost-first; the last
add_middleware call becomes the outermost wrapper.
"""
import logging
import time

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware

from app.config import settings

audit_logger = logging.getLogger("fastango.audit")


def configure_middleware(app: FastAPI) -> None:
    """Mount all centralized middlewares onto the FastAPI application."""

    # ── Audit & Timing (innermost) ──────────────────────────────────────────
    @app.middleware("http")
    async def audit_and_timing_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"

        audit_logger.info(
            "%s %s -> %d in %.2fms ip=%s ua=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            request.client.host if request.client else "unknown",
            request.headers.get("user-agent", "-"),
        )
        return response

    # ── Security Headers ────────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = (
            "geolocation=(), microphone=(), camera=()"
        )
        if settings.APP_ENV not in ("local", "test", "testing"):
            response.headers["Strict-Transport-Security"] = (
                "max-age=63072000; includeSubDomains"
            )
        return response

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept"],
    )

    # ── Trusted Host (outermost — added last) ───────────────────────────────
    # Rejects requests with a Host header outside the allowed list, blocking
    # Host-header injection / cache-poisoning before any other middleware runs.
    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=settings.ALLOWED_HOSTS,
    )
