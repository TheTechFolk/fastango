"""The limiter: that it limits, and that losing its storage does not take auth down."""

import pytest
from fastapi import FastAPI, Request
from httpx import ASGITransport, AsyncClient

from app.config import settings
from app.core.rate_limit import _build_limiter
from app.exceptions import configure_exceptions


def _app(monkeypatch, redis_url: str) -> FastAPI:
    monkeypatch.setattr(settings, "RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", redis_url)
    limiter = _build_limiter()

    app = FastAPI()
    app.state.limiter = limiter
    configure_exceptions(app)

    @app.get("/limited")
    @limiter.limit("2/minute")
    async def limited(request: Request):
        return {"error": False}

    return app


async def _statuses(app: FastAPI, n: int) -> list[int]:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        return [(await ac.get("/limited")).status_code for _ in range(n)]


@pytest.mark.asyncio
async def test_over_the_limit_is_a_429_in_the_envelope(monkeypatch):
    app = _app(monkeypatch, redis_url="")
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        assert [(await ac.get("/limited")).status_code for _ in range(2)] == [200, 200]
        resp = await ac.get("/limited")

    assert resp.status_code == 429
    assert resp.json()["error"] is True
    assert int(resp.headers["Retry-After"]) > 0


@pytest.mark.asyncio
async def test_unreachable_redis_falls_back_instead_of_500(monkeypatch):
    """Nothing listens on this port. Before the fallback every rate-limited
    route — login included — answered 500 for as long as Redis was down."""
    app = _app(monkeypatch, redis_url="redis://127.0.0.1:6399/0")
    # Still limited, just per-process: the third call is refused.
    assert await _statuses(app, 3) == [200, 200, 429]
