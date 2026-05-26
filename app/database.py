# app/database.py
from collections.abc import AsyncGenerator
from contextvars import ContextVar

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import declarative_base

from app.config import settings

# ── Async Engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    pool_size=settings.DB_POOL_SIZE,
    max_overflow=settings.DB_MAX_OVERFLOW,
    pool_pre_ping=True,
)

# ── Session Factory ───────────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)

# ── Declarative Base ──────────────────────────────────────────────────────────
Base = declarative_base()

# ── Context Var & Session Helpers ─────────────────────────────────────────────
db_session_ctx: ContextVar[AsyncSession] = ContextVar("db_session")


def get_db_session() -> AsyncSession:
    """
    Retrieve the current request-scoped database session.
    """
    try:
        return db_session_ctx.get()
    except LookupError:
        raise RuntimeError("No database session in the current context.")


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Yield a SQLAlchemy AsyncSession as a FastAPI dependency.
    Automatically commits on success or rolls back on exception.
    """
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def inject_db_session_context(db: AsyncSession = Depends(get_db)):
    """
    FastAPI dependency to bind the request-scoped database session.
    """
    token = db_session_ctx.set(db)
    try:
        yield
    finally:
        db_session_ctx.reset(token)
