"""The uncommitted-write guard, through the real get_db.

Every other API test overrides get_db, so none of them can see this. It is the
one promise that depends on *when* FastAPI runs a dependency's teardown: from
0.118 that is after the response has been sent unless the dependency is
function-scoped, and the guard then raises into the void — the client gets a
200 and the write is gone.
"""

from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import (
    Base,
    DbSessionContext,
    async_session_factory,
    engine,
    get_db_session,
)
from app.exceptions import configure_exceptions
from app.modules.auth.models import Auth


async def test_a_write_without_atomic_is_a_500_and_is_not_persisted():
    app = FastAPI()
    configure_exceptions(app)

    @app.post("/leak", dependencies=[DbSessionContext])
    async def leak():
        db = get_db_session()
        db.add(Auth(email="leak@example.com", password="x"))
        await db.flush()  # written, never committed — no atomic()
        return {"error": False}

    try:
        # The app's own engine: on SQLite that is a different in-memory
        # database from the fixtures', so it needs its own tables.
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://testserver") as client:
            resp = await client.post("/leak")

        assert resp.status_code == 500
        assert resp.json()["error"] is True

        async with async_session_factory() as session:
            assert (await session.execute(select(Auth))).scalars().all() == []
    finally:
        # Pooled asyncpg connections cannot outlive this test's event loop.
        await engine.dispose()
