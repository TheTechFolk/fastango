# app/core/registry.py
"""
Fastango — Module Registry

Auto-discovers every package under app/modules/ and mounts the ones that expose
a ModuleConfig subclass in their apps.py. Django's INSTALLED_APPS without the
list: drop a directory in, it mounts. There is no registration step.

A module opts in to routing by creating apps.py with a ModuleConfig subclass.
A module without apps.py (e.g. `common`) is skipped — its models.py is still
imported so SQLAlchemy metadata stays complete for Alembic.

Routes mount under one of two roots, and that placement is what decides whether
a token is required:

    ModuleConfig.router         -> /private/api/v1/<prefix>   (token required)
    ModuleConfig.public_router  -> /public/api/v1/<prefix>    (open)

The auth middleware gates on the "/public/" prefix alone, so a module that
declares nothing is private by default and exposing an endpoint has to be a
deliberate act.
"""

import importlib
import logging
import pkgutil
from collections.abc import Iterator

from fastapi import APIRouter, Depends, FastAPI

from app.config import settings
from app.core.security import bearer_scheme, get_current_user_code
from app.database import inject_db_session_context

logger = logging.getLogger("fastango.registry")

# Version last, so the auth middleware matches one fixed prefix that never has
# to learn about API versions — /public/api/v2 stays public for free.
PRIVATE_ROOT = "/private/api/v1"
PUBLIC_ROOT = "/public/api/v1"


class ModuleConfig:
    """Per-module configuration, declared in app/modules/<name>/apps.py.

    Subclass it and override the class attributes:

        class AuthConfig(ModuleConfig):
            name = "auth"
            prefix = "/auth"
            tags = ["Auth"]
            public_router = public_router   # /public/api/v1/auth/...
            router = private_router         # /private/api/v1/auth/...
            # Optional: guards applied to EVERY route in this module,
            # e.g. dependencies = [Depends(require_role(RoleType.ADMIN))]
            dependencies = []
    """

    name: str = ""
    prefix: str = ""
    tags: list[str] = []
    dependencies: list = []

    # Mounted under PRIVATE_ROOT — every route needs a valid access token.
    # Named plainly `router` so a module that thinks about none of this is
    # private by default.
    router: APIRouter | None = None
    # Mounted under PUBLIC_ROOT — reachable with no token. Opt in explicitly.
    public_router: APIRouter | None = None

    async def on_startup(self) -> None:
        """Override to run code when the application starts."""

    async def on_shutdown(self) -> None:
        """Override to run code when the application shuts down."""


def _iter_module_names() -> Iterator[str]:
    """Yield every package name directly under app.modules."""
    import app.modules as modules_pkg

    for _, name, ispkg in pkgutil.iter_modules(modules_pkg.__path__):
        if ispkg:
            yield name


def import_all_models() -> None:
    """Import every app.modules.*.models so Base.metadata is fully populated.

    Used by both the app boot and Alembic's env.py — guarantees migrations see
    the same tables the running app does.
    """
    for name in _iter_module_names():
        try:
            importlib.import_module(f"app.modules.{name}.models")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{name}.models":
                continue
            raise


def _module_enabled(name: str) -> bool:
    """Decide whether a module's router gets mounted, based on settings.

    DISABLED_MODULES always wins; otherwise an empty ENABLED_MODULES means
    "mount everything". Models of disabled modules are still imported so
    Alembic migrations stay complete (disabled ≠ uninstalled).
    """
    if name in settings.DISABLED_MODULES:
        return False
    return not settings.ENABLED_MODULES or name in settings.ENABLED_MODULES


def _find_config_class(module) -> type[ModuleConfig] | None:
    """Find the ModuleConfig subclass *defined in* `module`.

    The `__module__` check matters: without it this returns whatever sorts
    first in dir(), so an imported config from another module — or a second
    config declared alongside — silently wins and the wrong router mounts.
    """
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, ModuleConfig)
            and obj is not ModuleConfig
            and obj.__module__ == module.__name__
        ):
            return obj
    return None


def discover_modules(app: FastAPI) -> list[ModuleConfig]:
    """Walk app/modules/*, import models, mount routers.

    Each module's private and public routers mount under their own roots, so a
    route's URL states its auth requirement.

    Returns the instantiated configs so the app lifespan can dispatch their
    on_startup / on_shutdown hooks.
    """
    import_all_models()

    # The DB session binds here rather than on the FastAPI app: as an app-level
    # dependency it opened a pooled connection for every /health probe.
    #
    # The private root also carries its own auth guard rather than trusting the
    # URL-prefix match in the middleware to be the only thing between /private
    # and the world. Two independent checks, so one mounting mistake is not an
    # opening. bearer_scheme is what gives Swagger the Authorize button.
    private_router = APIRouter(
        prefix=PRIVATE_ROOT,
        dependencies=[
            Depends(inject_db_session_context),
            Depends(bearer_scheme),
            Depends(get_current_user_code),
        ],
    )
    public_router = APIRouter(
        prefix=PUBLIC_ROOT,
        dependencies=[Depends(inject_db_session_context)],
    )
    configs: list[ModuleConfig] = []

    for name in _iter_module_names():
        if not _module_enabled(name):
            logger.info("Module '%s' disabled via settings — not mounted", name)
            continue

        try:
            apps_mod = importlib.import_module(f"app.modules.{name}.apps")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{name}.apps":
                logger.debug("Skipping module '%s' — no apps.py", name)
                continue
            raise

        config_cls = _find_config_class(apps_mod)
        if config_cls is None:
            logger.warning("app.modules.%s.apps has no ModuleConfig subclass — skipping", name)
            continue

        config = config_cls()
        for module_router, parent, root in (
            (config.router, private_router, PRIVATE_ROOT),
            (config.public_router, public_router, PUBLIC_ROOT),
        ):
            if module_router is None:
                continue
            parent.include_router(
                module_router,
                prefix=config.prefix,
                tags=list(config.tags),
                dependencies=list(config.dependencies),
            )
            logger.info("Mounted module '%s' at %s%s", config.name, root, config.prefix)
        configs.append(config)

    app.include_router(private_router)
    app.include_router(public_router)
    return configs
