# app/main.py
"""
Fastango — Application Factory

Boots the FastAPI instance, wires centralized middleware and exception handlers,
then auto-discovers every module under app/modules/ and mounts the ones that
expose a ModuleConfig in apps.py.
"""

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from sqlalchemy import text

from app.config import settings
from app.core.rate_limit import limiter
from app.core.registry import ModuleConfig, discover_modules
from app.database import engine
from app.exceptions import configure_exceptions
from app.logging_config import configure_logging
from app.middleware import configure_middleware

logger = logging.getLogger("fastango")

# Populated by discover_modules() at import time, before lifespan runs.
module_configs: list[ModuleConfig] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Dispatch startup/shutdown hooks to every discovered module."""
    configure_logging()
    logger.info("🚀  Fastango is starting up — environment: %s", settings.APP_ENV)
    for cfg in module_configs:
        await cfg.on_startup()
    yield
    for cfg in reversed(module_configs):
        # One module failing to shut down must not skip the rest, and must not
        # skip engine.dispose() below — that would leak pooled connections.
        try:
            await cfg.on_shutdown()
        except Exception:
            logger.exception("Shutdown hook failed for module %s", cfg.name)
    # Close pooled connections while the loop is still running. Without this the
    # loop closes first and asyncpg warns its cancel coroutine was never awaited.
    await engine.dispose()
    logger.info("🛑  Fastango is shutting down.")


# The docs publish every private route, schema and field name. Anonymous in
# production is a free map of the attack surface, so they exist in dev only.
_docs_enabled = settings.is_dev

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Fastango — a Django-inspired modular FastAPI template.",
    docs_url="/docs" if _docs_enabled else None,
    redoc_url="/redoc" if _docs_enabled else None,
    openapi_url="/openapi.json" if _docs_enabled else None,
    lifespan=lifespan,
)

# slowapi requires the limiter on app.state. Its 429 handler is registered in
# configure_exceptions() rather than here, so the response keeps the envelope.
app.state.limiter = limiter

configure_middleware(app)
configure_exceptions(app)


@app.get("/health", tags=["Health"], summary="Liveness check")
async def health_check():
    """Is the process up. Deliberately touches nothing — a liveness probe that
    fails on a dependency outage gets the container killed instead of drained."""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


@app.get("/health/ready", tags=["Health"], summary="Readiness check")
async def readiness_check():
    """Can the process actually serve. Checks the database.

    The liveness probe returns ok while Postgres is down, which is correct for
    liveness and useless for a load balancer — this is the one to route on.
    """
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))
    return {"status": "ready", "database": "ok"}


module_configs.extend(discover_modules(app))
