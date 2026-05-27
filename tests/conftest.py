# tests/conftest.py
"""
Shared pytest fixtures for the Fastango test suite.
Uses an in-memory SQLite database (via aiosqlite) for fast, isolated tests.
"""

# IMPORTANT: env vars are set BEFORE any app import so pydantic-settings picks
# them up. APP_ENV=test enables the dev-only auth fallback; RATE_LIMIT_ENABLED
# turns slowapi into a no-op so per-IP limits don't trip across test runs.
import os

os.environ.setdefault("APP_ENV", "test")
os.environ.setdefault("RATE_LIMIT_ENABLED", "false")

import asyncio
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.database import Base, _has_uncommitted_writes, get_db
from app.main import app

# ── In-Memory Test Database ───────────────────────────────────────────────────
TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(TEST_DATABASE_URL, echo=False)
TestSessionFactory = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@pytest.fixture(scope="session")
def event_loop():
    """Use a single event loop for the entire test session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


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
    """
    Yield a test database session. Transaction management is service-owned
    (services use `async with db.begin():`), matching production `get_db()`,
    and the same uncommitted-write guard is enforced here.
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
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Yield a test HTTP client with the database dependency overridden
    to use the isolated test session.
    """

    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
