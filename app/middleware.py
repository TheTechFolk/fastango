# app/middleware.py
"""
Fastango — Centralized Middleware Configurations

Middlewares are added innermost-first; the last add_middleware call becomes the
outermost wrapper. Request flow, outermost to innermost:

    TrustedHost -> CORS -> SecurityHeaders -> RequestId -> Audit -> Auth -> router
"""

import logging
import time

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.constants import UNAUTHORIZED_MSG
from app.core.context import (
    REQUEST_ID_HEADER,
    client_ip,
    new_request_id,
    request_id_ctx,
)
from app.core.registry import PUBLIC_ROOT
from app.core.responses import error_response
from app.core.security import decode_token

audit_logger = logging.getLogger("fastango.audit")

# Everything under here is reachable without a token. The trailing slash is
# deliberate — a bare "/public" prefix would also exempt "/publicity".
PUBLIC_PREFIX = f"{PUBLIC_ROOT.split('/api')[0]}/"  # "/public/"

# Routes no module owns, so they can't declare themselves via public_router.
# The docs URLs are only in here when the app actually serves them — see
# public_paths(); publishing the private API surface anonymously in production
# is not something a path allowlist should decide on its own.
_BASE_PUBLIC_PATHS = frozenset({"/health", "/health/ready", "/favicon.ico"})
_DOCS_PATHS = frozenset({"/docs", "/redoc", "/openapi.json"})

# Probes are the majority of traffic in any orchestrated deployment and none of
# it is interesting. Logged at DEBUG instead of INFO.
_LOW_SIGNAL_PATHS = frozenset({"/health", "/health/ready"})


def public_paths() -> frozenset[str]:
    """Paths reachable without a token, for this environment."""
    if settings.is_dev:
        return _BASE_PUBLIC_PATHS | _DOCS_PATHS
    return _BASE_PUBLIC_PATHS


def _is_public(request: Request) -> bool:
    """True when the request may proceed without authentication."""
    # CORS preflight carries no Authorization header — blocking it breaks every
    # browser client before the real request is ever sent.
    if request.method == "OPTIONS":
        return True
    path = request.url.path
    return path in public_paths() or path.startswith(PUBLIC_PREFIX)


def configure_middleware(app: FastAPI) -> None:
    """Mount all centralized middlewares onto the FastAPI application."""

    # ── Authentication (innermost) ──────────────────────────────────────────
    # Default-deny: everything needs a valid access token unless its path is
    # public. Declared before CORS so CORS stays outside it and 401 responses
    # still carry their CORS headers.
    #
    # There is deliberately no environment that relaxes this. Tests mint a real
    # token instead — see the `client` fixture in tests/conftest.py.
    @app.middleware("http")
    async def auth_middleware(request: Request, call_next):
        if _is_public(request):
            return await call_next(request)

        header = request.headers.get("Authorization", "")
        if not header.startswith("Bearer "):
            audit_logger.warning("Blocked unauthenticated request to %s", request.url.path)
            return _unauthorized(UNAUTHORIZED_MSG)

        try:
            # decode_token raises HTTPException, but middleware runs outside
            # FastAPI's exception handlers — a raised one would surface as a
            # 500. Catch it and build the response by hand.
            payload = decode_token(header.removeprefix("Bearer ").strip())
        except HTTPException as exc:
            return _unauthorized(str(exc.detail))

        request.state.user_code = payload.get("sub")
        request.state.role = payload.get("role", "USER")
        return await call_next(request)

    # ── Audit & Timing ──────────────────────────────────────────────────────
    @app.middleware("http")
    async def audit_and_timing_middleware(request: Request, call_next):
        start_time = time.perf_counter()
        response = await call_next(request)
        elapsed_ms = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{elapsed_ms:.2f}ms"

        level = logging.DEBUG if request.url.path in _LOW_SIGNAL_PATHS else logging.INFO
        audit_logger.log(
            level,
            "%s %s -> %d in %.2fms ip=%s user=%s ua=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            client_ip(request),
            getattr(request.state, "user_code", "-"),
            request.headers.get("user-agent", "-"),
        )
        return response

    # ── Request correlation ─────────────────────────────────────────────────
    # Outside the audit layer so the id exists before anything logs, and reset
    # afterwards so a pooled worker never inherits the previous request's id.
    @app.middleware("http")
    async def request_id_middleware(request: Request, call_next):
        incoming = request.headers.get(REQUEST_ID_HEADER, "").strip()
        # Trust an upstream id only if it looks like one — it lands in logs.
        request_id = incoming if incoming.isalnum() and len(incoming) <= 64 else new_request_id()
        token = request_id_ctx.set(request_id)
        try:
            response = await call_next(request)
        finally:
            request_id_ctx.reset(token)
        response.headers[REQUEST_ID_HEADER] = request_id
        return response

    # ── Security Headers ────────────────────────────────────────────────────
    @app.middleware("http")
    async def security_headers_middleware(request: Request, call_next):
        response = await call_next(request)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        response.headers["Permissions-Policy"] = "geolocation=(), microphone=(), camera=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        response.headers["Cross-Origin-Resource-Policy"] = "same-origin"
        # This is a JSON API — nothing it returns should ever be executed or
        # framed. Swagger UI needs its own inline styles, so relax it only for
        # the docs routes, which exist in dev only.
        if request.url.path in _DOCS_PATHS:
            response.headers["Content-Security-Policy"] = (
                "default-src 'self'; img-src 'self' data:; "
                "script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'"
            )
        else:
            response.headers["Content-Security-Policy"] = (
                "default-src 'none'; frame-ancestors 'none'"
            )
        if not settings.is_dev:
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response

    # ── CORS ────────────────────────────────────────────────────────────────
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Accept", REQUEST_ID_HEADER],
        expose_headers=[REQUEST_ID_HEADER],
    )

    # ── Trusted Host (outermost — added last) ───────────────────────────────
    # Rejects requests with a Host header outside the allowed list, blocking
    # Host-header injection / cache-poisoning before any other middleware runs.
    app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.ALLOWED_HOSTS)


def _unauthorized(message: str) -> JSONResponse:
    """401 in the app's standard envelope, with the Bearer challenge intact."""
    return JSONResponse(
        status_code=401,
        content=error_response(message=message),
        headers={"WWW-Authenticate": "Bearer"},
    )
