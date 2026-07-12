# tests/test_registry.py
"""
Tests for module discovery: enable/disable via settings and module-level
dependency pass-through.
"""

import types

from fastapi import APIRouter, Depends, FastAPI, HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.core import registry
from app.core.registry import ModuleConfig, _module_enabled, discover_modules


# ── _module_enabled unit tests ────────────────────────────────────────────────
def test_all_modules_enabled_by_default(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])
    assert _module_enabled("home") is True
    assert _module_enabled("anything") is True


def test_enabled_list_acts_as_whitelist(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", ["auth", "profile"])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])
    assert _module_enabled("auth") is True
    assert _module_enabled("home") is False


def test_disabled_list_wins_over_enabled(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", ["auth"])
    monkeypatch.setattr(settings, "DISABLED_MODULES", ["auth"])
    assert _module_enabled("auth") is False


# ── discover_modules integration ─────────────────────────────────────────────
def test_disabled_module_not_mounted(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", ["home"])

    app = FastAPI()
    discover_modules(app)

    paths = {route.path for route in app.routes}
    assert "/api/v1/home" not in paths
    assert "/api/v1/profile" in paths
    assert "/api/v1/auth/login" in paths


def test_all_modules_mounted_when_lists_empty(monkeypatch):
    monkeypatch.setattr(settings, "ENABLED_MODULES", [])
    monkeypatch.setattr(settings, "DISABLED_MODULES", [])

    app = FastAPI()
    discover_modules(app)

    paths = {route.path for route in app.routes}
    assert {"/api/v1/home", "/api/v1/profile", "/api/v1/auth/login"} <= paths


# ── Module-level dependencies ─────────────────────────────────────────────────
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

    DummyConfig.router = dummy_router
    DummyConfig.dependencies = [Depends(deny)]

    dummy_apps = types.SimpleNamespace(DummyConfig=DummyConfig)
    monkeypatch.setattr(registry, "_iter_module_names", lambda: iter(["dummy"]))
    monkeypatch.setattr(registry, "import_all_models", lambda: None)
    monkeypatch.setattr(registry.importlib, "import_module", lambda name: dummy_apps)

    app = FastAPI()
    discover_modules(app)

    client = TestClient(app)
    response = client.get("/api/v1/dummy/ping")
    assert response.status_code == 418
    assert response.json()["detail"] == "module guard fired"
