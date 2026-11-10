"""Lifespan hooks and the readiness probe — what an orchestrator depends on."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

from sqlalchemy.exc import OperationalError

from app import main
from app.core.registry import ModuleConfig


class _Recorder(ModuleConfig):
    name = "recorder"

    def __init__(self) -> None:
        self.events: list[str] = []

    async def on_startup(self) -> None:
        self.events.append("startup")

    async def on_shutdown(self) -> None:
        self.events.append("shutdown")


class _BrokenShutdown(ModuleConfig):
    name = "broken"

    async def on_shutdown(self) -> None:
        raise RuntimeError("boom")


async def test_lifespan_runs_hooks_and_survives_a_failing_shutdown(monkeypatch):
    """One module failing to shut down must not skip the others, and must not
    skip closing the connection pool."""
    recorder = _Recorder()
    dispose = AsyncMock()
    # Shutdown runs in reverse, so the broken hook fires before the recorder's.
    monkeypatch.setattr(main, "module_configs", [recorder, _BrokenShutdown()])
    monkeypatch.setattr(main, "configure_logging", lambda: None)
    # A stand-in rather than a patched method: AsyncEngine's attributes are read-only.
    monkeypatch.setattr(main, "engine", SimpleNamespace(dispose=dispose))

    async with main.lifespan(main.app):
        assert recorder.events == ["startup"]

    assert recorder.events == ["startup", "shutdown"]
    dispose.assert_awaited_once()


async def test_ready_when_the_database_answers(anon_client):
    resp = await anon_client.get("/health/ready")
    # Close the pooled connection on this test's event loop, not a later one.
    await main.engine.dispose()

    assert resp.status_code == 200
    assert resp.json() == {"status": "ready", "database": "ok"}


async def test_not_ready_is_503_when_the_database_is_down(anon_client, monkeypatch):
    """503 with a retry hint, in the envelope — not an opaque 500. This is the
    signal a load balancer uses to stop routing here."""

    def refuse():
        raise OperationalError("SELECT 1", {}, Exception("connection refused"))

    monkeypatch.setattr(main, "engine", SimpleNamespace(connect=refuse))
    resp = await anon_client.get("/health/ready")

    assert resp.status_code == 503
    assert resp.headers["Retry-After"] == "5"
    assert resp.json()["error"] is True
