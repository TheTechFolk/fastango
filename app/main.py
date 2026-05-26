# app/main.py
"""
Fastango — Application Factory

Boots the FastAPI instance, wires centralized middleware and exception
handlers, then auto-discovers every module under app/modules/ and mounts
the ones that expose a ModuleConfig in apps.py.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.config import settings
from app.core.rate_limit import limiter
from app.core.registry import ModuleConfig, discover_modules
from app.database import inject_db_session_context
from app.exceptions import configure_exceptions
from app.middleware import configure_middleware

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fastango")

# Populated by discover_modules() at import time, before lifespan runs.
module_configs: list[ModuleConfig] = []


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Dispatch startup/shutdown hooks to every discovered module."""
    logger.info("🚀  Fastango is starting up — environment: %s", settings.APP_ENV)
    for cfg in module_configs:
        await cfg.on_startup()
    yield
    for cfg in reversed(module_configs):
        await cfg.on_shutdown()
    logger.info("🛑  Fastango is shutting down.")


app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="Fastango — A Django-inspired modular FastAPI framework.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
    dependencies=[Depends(inject_db_session_context)],
)

# Rate-limit wiring — slowapi requires the limiter on app.state and its own
# exception handler for 429 responses.
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

configure_middleware(app)
configure_exceptions(app)


@app.get("/health", tags=["Health"], summary="Service health check")
async def health_check():
    """Returns a simple alive signal used by load balancers and Docker health checks."""
    return {"status": "ok", "service": settings.APP_NAME, "version": settings.APP_VERSION}


module_configs.extend(discover_modules(app))
