"""Module discovery: enable/disable via settings, dual mounting, config lookup."""

import types

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.core import registry
from app.core.registry import (
    PRIVATE_ROOT,
    PUBLIC_ROOT,
    ModuleConfig,
    _find_config_class,
    _module_enabled,
    discover_modules,
)


# ── _module_enabled ───────────────────────────────────────────────────────────
def test_all_modules_enabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])
    assert _module_enabled("auth") is True
    assert _module_enabled("anything") is True


def test_enabled_list_acts_as_whitelist(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", ["auth"])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])
    assert _module_enabled("auth") is True
    assert _module_enabled("billing") is False


def test_disabled_list_wins_over_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", ["auth"])
    monkeypatch.setattr(settings, "DISABLED_MODULES", ["auth"])
    assert _module_enabled("auth") is False


# ── _find_config_class ────────────────────────────────────────────────────────
def test_find_config_ignores_imported_configs():
    """A config imported into apps.py must not be mistaken for the module's own.

    Without the __module__ check this returns whatever sorts first in dir(), so
    an imported config silently wins and the wrong router mounts.
    """

    class AaaImportedConfig(ModuleConfig):
        name = "imported"

    class OwnConfig(ModuleConfig):
        name = "own"

    fake = types.ModuleType("app.modules.fake.apps")
    AaaImportedConfig.__module__ = "app.modules.elsewhere.apps"
    OwnConfig.__module__ = "app.modules.fake.apps"
    fake.AaaImportedConfig = AaaImportedConfig
    fake.OwnConfig = OwnConfig

    assert _find_config_class(fake) is OwnConfig


def test_find_config_returns_none_without_a_config():
    fake = types.ModuleType("app.modules.empty.apps")
    assert _find_config_class(fake) is None


# ── discover_modules ──────────────────────────────────────────────────────────
def test_auth_mounts_under_both_roots(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])

    app = FastAPI()
    discover_modules(app)

    paths = {route.path for route in app.routes}
    assert f"{PUBLIC_ROOT}/auth/login" in paths
    assert f"{PUBLIC_ROOT}/auth/register" in paths
    assert f"{PUBLIC_ROOT}/auth/refresh" in paths
    assert f"{PRIVATE_ROOT}/auth/me" in paths


def test_disabled_module_not_mounted(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", ["auth"])

    app = FastAPI()
    discover_modules(app)

    paths = {route.path for route in app.routes}
    assert f"{PUBLIC_ROOT}/auth/login" not in paths


def test_module_level_dependencies_applied(monkeypatch):
    """A dependency declared on ModuleConfig must guard every route in the module."""

    async def deny():
        raise HTTPException(status_code=418, detail="module guard fired")

    dummy_router = APIRouter()

    @dummy_router.get("/ping")
    async def ping():
        return {"ok": True}

    class DummyConfig(ModuleConfig):
        name = "dummy"
        prefix = "/dummy"
        tags = ["Dummy"]

    # Mounted public so this test isolates the module dependency. On the private
    # root the router's own auth guard fires first — see the test below, which
    # is the point of having two independent checks.
    DummyConfig.public_router = dummy_router
    DummyConfig.dependencies = [Depends(deny)]
    DummyConfig.__module__ = "app.modules.dummy.apps"

    dummy_apps = types.ModuleType("app.modules.dummy.apps")
    dummy_apps.DummyConfig = DummyConfig

    monkeypatch.setattr(registry, "_iter_module_names", lambda: iter(["dummy"]))
    monkeypatch.setattr(registry, "import_all_models", lambda: None)
    monkeypatch.setattr(registry.importlib, "import_module", lambda name: dummy_apps)

    app = FastAPI()
    discover_modules(app)

    response = TestClient(app).get(f"{PUBLIC_ROOT}/dummy/ping")
    assert response.status_code == 418
    assert response.json()["detail"] == "module guard fired"


def test_private_router_guards_itself_without_the_middleware():
    """The second of the two independent checks on /private.

    This app is built without configure_middleware(), so the URL-prefix check
    that normally rejects an anonymous request is absent. The route-level guard
    on the private router must still refuse — one mounting mistake is then not
    an opening.
    """
    app = FastAPI()
    discover_modules(app)

    response = TestClient(app).get(f"{PRIVATE_ROOT}/auth/me")
    assert response.status_code == 401
