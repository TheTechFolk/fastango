# app/core/registry.py
"""
Fastango — Module Registry

Auto-discovers every package under app/modules/ and mounts the ones that
expose a ModuleConfig subclass in their apps.py. Replaces the hand-edited
app/router.py and app/models.py registries.

A module opts in to routing by creating apps.py with a ModuleConfig subclass.
A module without apps.py (e.g. `common`) is skipped — its models.py is still
imported so SQLAlchemy metadata stays complete for Alembic.
"""
import importlib
import logging
import pkgutil
from typing import Iterator

from fastapi import APIRouter, FastAPI

logger = logging.getLogger("fastango.registry")


class ModuleConfig:
    """
    Per-module configuration, declared in app/modules/<name>/apps.py.

    Subclass it and override the class attributes:

        class AuthConfig(ModuleConfig):
            name = "auth"
            router = router
            prefix = "/auth"
            tags = ["Auth — Admin"]
    """

    name: str = ""
    router: APIRouter | None = None
    prefix: str = ""
    tags: list[str] = []

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
    """
    Import every app.modules.*.models so SQLAlchemy's Base.metadata is fully
    populated. Used by both the app boot and Alembic's env.py — guarantees
    migrations see the same tables the running app does.
    """
    for name in _iter_module_names():
        try:
            importlib.import_module(f"app.modules.{name}.models")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{name}.models":
                continue
            raise


def _find_config_class(module) -> type[ModuleConfig] | None:
    """Find the first ModuleConfig subclass defined in `module`."""
    for attr_name in dir(module):
        obj = getattr(module, attr_name)
        if (
            isinstance(obj, type)
            and issubclass(obj, ModuleConfig)
            and obj is not ModuleConfig
        ):
            return obj
    return None


def discover_modules(app: FastAPI, prefix: str = "/api/v1") -> list[ModuleConfig]:
    """
    Walk app/modules/*, import models, mount routers from any module that
    declares a ModuleConfig subclass in apps.py.

    Returns the instantiated configs so the app lifespan can dispatch their
    on_startup / on_shutdown hooks.
    """
    import_all_models()

    api_router = APIRouter(prefix=prefix)
    configs: list[ModuleConfig] = []

    for name in _iter_module_names():
        try:
            apps_mod = importlib.import_module(f"app.modules.{name}.apps")
        except ModuleNotFoundError as exc:
            if exc.name == f"app.modules.{name}.apps":
                logger.debug("Skipping module '%s' — no apps.py", name)
                continue
            raise

        config_cls = _find_config_class(apps_mod)
        if config_cls is None:
            logger.warning(
                "app.modules.%s.apps has no ModuleConfig subclass — skipping", name
            )
            continue

        config = config_cls()
        if config.router is not None:
            api_router.include_router(
                config.router,
                prefix=config.prefix,
                tags=list(config.tags),
            )
            logger.info(
                "Mounted module '%s' at %s%s", config.name, prefix, config.prefix
            )
        configs.append(config)

    app.include_router(api_router)
    return configs
