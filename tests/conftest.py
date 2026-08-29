# tests/conftest.py
"""
Shared pytest fixtures for the Fastango test suite.
Uses an in-memory SQLite database (via aiosqlite) for fast, isolated tests.
"""

# IMPORTANT: env vars are set BEFORE any app import so pydantic-settings picks
# them up, and environment takes precedence over local.env. RATE_LIMIT_ENABLED
# turns slowapi into a no-op so per-IP limits don't trip across test runs — the
# tests that exercise the limiter re-enable it. SECRET_KEY and DATABASE_URL are
# required with no defaults; setting them here is what lets the suite run
# without a local.env on disk.
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")
# In-memory limiter storage: the suite must not need a Redis to run.
os.environ.setdefault("REDIS_URL", "")
os.environ.setdefault("SECRET_KEY", "test-secret-key-not-used-outside-the-test-suite")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


import uuid
from collections.abc import AsyncGenerator

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.constants import RoleType
from app.database import Base, _has_uncommitted_writes, db_session_ctx, get_db
from app.main import app
from app.modules.auth.utils import create_access_token

# ── In-Memory Test Database ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

# The identity the authenticated fixtures speak as. Real UUIDs because the
# `sub` claim is parsed as one.
TEST_USER_CODE = str(uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6"))
TEST_ADMIN_CODE = str(uuid.UUID("6b1f2c98-7d43-4a5e-9c21-0f8ab3d5e7c4"))


@event.listens_for(test_engine.sync_engine, "connect")
def _enforce_sqlite_foreign_keys(dbapi_connection, _record):
    """Turn on FK enforcement, which SQLite leaves off by default.

    Without this the foreign keys are declared and never checked, so a suite
    that passes proves nothing about referential integrity — and Postgres would
    reject in production what SQLite accepted here.
    """
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_database():
    """Create all tables before each test and drop them after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a test database session.

    Transaction management is service-owned (services use `async with
    db.begin():`), matching production `get_db()`, and the same
    uncommitted-write guard is enforced here.
    """
    async with TestSessionFactory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            if _has_uncommitted_writes(session):
                await session.rollback()
                raise RuntimeError(
                    "Test left uncommitted writes on the session. Wrap setup "
                    "mutations in `async with db_session.begin():`."
                )


@pytest_asyncio.fixture
async def request_session(db_session: AsyncSession) -> AsyncGenerator[AsyncSession, None]:
    """Prime the request-scoped session ContextVar.

    Services resolve their session through `get_db_session()` rather than being
    handed one, so calling a service directly — without an HTTP request in
    flight — raises `RuntimeError: No database session in the current context`.
    Only the ASGI dependency sets that ContextVar in production.

    Reset afterwards so nothing leaks into the next test. This fixture is the
    entire cost of the service-locator trade documented in app/database.py.
    """
    token = db_session_ctx.set(db_session)
    try:
        yield db_session
    finally:
        db_session_ctx.reset(token)


def _override_get_db(db_session: AsyncSession):
    """The get_db replacement that hands every request the test's session."""

    async def override():
        try:
            yield db_session
        finally:
            # Production hands every request a brand-new session, so nothing a
            # request reads can leave a transaction open for the next one. The
            # tests share a single session, which does not — and SQLAlchemy
            # refuses `db.begin()` once a read has implicitly opened one.
            # Rolling back a read-only leftover reproduces the production
            # lifecycle; anything with pending writes is left alone for the
            # uncommitted-write guard to catch.
            if db_session.in_transaction() and not _has_uncommitted_writes(db_session):
                await db_session.rollback()

    return override


def auth_header(user_code: str = TEST_USER_CODE, role: str = RoleType.USER.value) -> dict[str, str]:
    """A real signed Bearer token.

    Tests mint one rather than relying on an environment that waives auth. The
    bypass this replaces lived in production code and turned APP_ENV into a
    switch that disabled authentication for the whole app.
    """
    return {"Authorization": f"Bearer {create_access_token(subject=user_code, role=role)}"}


@pytest_asyncio.fixture
async def anon_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An unauthenticated client. Private routes answer 401 through this one."""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """An HTTP client authenticated as a normal user.

    Authentication is real: every request carries a signed token that the auth
    middleware decodes exactly as it would in production.
    """
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=auth_header(),
    ) as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def admin_client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """The same, speaking as an ADMIN."""
    app.dependency_overrides[get_db] = _override_get_db(db_session)
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
        headers=auth_header(TEST_ADMIN_CODE, RoleType.ADMIN.value),
    ) as ac:
        yield ac
    app.dependency_overrides.clear()
