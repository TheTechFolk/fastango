# app/database.py
from collections.abc import AsyncGenerator
from contextvars import ContextVar

from fastapi import Depends
from sqlalchemy import event
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Session

from app.config import settings


def _engine_options() -> dict:
    """Pool settings, where the driver has a pool to configure.

    SQLite runs on StaticPool and rejects pool_size/max_overflow outright, so
    passing them unconditionally makes this module unimportable under the URL
    the tests use.
    """
    if settings.DATABASE_URL.startswith("sqlite"):
        return {}
    return {
        "pool_size": settings.DB_POOL_SIZE,
        "max_overflow": settings.DB_MAX_OVERFLOW,
        # Recycle before a proxy or NAT idle-timeout closes a pooled connection
        # underneath us — pre-ping alone turns that into a retry on every checkout.
        "pool_recycle": settings.DB_POOL_RECYCLE_SECONDS,
        "pool_pre_ping": True,
    }


# ── Async Engine ──────────────────────────────────────────────────────────────
engine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DB_ECHO,
    **_engine_options(),
)

# ── Session Factory ───────────────────────────────────────────────────────────
async_session_factory = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
)


# ── Declarative Base ──────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    """SQLAlchemy 2.0 declarative base, matching the Mapped/mapped_column models."""


# ── Context Var & Session Helpers ─────────────────────────────────────────────
# This is a service locator, and that is a deliberate trade: it keeps `db` out of
# every service signature and every handler one line. The cost is that a service
# cannot be called outside a request without priming this — see the
# `request_session` fixture in tests/conftest.py. Do not replace it with an
# optional `db` parameter; that reintroduces the nested-transaction bug the
# write guard below exists to catch.
db_session_ctx: ContextVar[AsyncSession] = ContextVar("db_session")


def get_db_session() -> AsyncSession:
    """Retrieve the current request-scoped database session."""
    try:
        return db_session_ctx.get()
    except LookupError as exc:
        raise RuntimeError("No database session in the current context.") from exc


# ── Uncommitted-write guard ───────────────────────────────────────────────────
# Tracks whether the session has writes that need a commit. Without this guard,
# a service that mutates the DB without `async with db.begin():` would silently
# lose its work — the session closes, the open transaction rolls back, and the
# request still returns 200. Better to fail loud.


@event.listens_for(Session, "after_flush")
def _flag_pending_writes(session: Session, flush_context) -> None:
    session.info["has_pending_writes"] = True


@event.listens_for(Session, "after_commit")
def _clear_on_commit(session: Session) -> None:
    session.info["has_pending_writes"] = False


@event.listens_for(Session, "after_rollback")
def _clear_on_rollback(session: Session) -> None:
    session.info["has_pending_writes"] = False


def _has_uncommitted_writes(session: AsyncSession) -> bool:
    """True if the session has dirty/new/deleted objects or unflushed-committed work."""
    sync = session.sync_session
    return bool(sync.info.get("has_pending_writes") or sync.new or sync.dirty or sync.deleted)


# ── FastAPI Dependency ────────────────────────────────────────────────────────
async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield a SQLAlchemy AsyncSession as a FastAPI dependency.

    Transaction management is owned by services (`async with db.begin():`).
    On request end this dependency:
      - rolls back on an unhandled exception, or
      - raises RuntimeError if writes are still pending — catches the bug
        where a service mutated the DB without an explicit transaction.
    """
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        else:
            if _has_uncommitted_writes(session):
                await session.rollback()
                raise RuntimeError(
                    "Uncommitted writes detected at request end. Wrap service "
                    "mutations in `async with db.begin():` so the transaction "
                    "boundary is explicit."
                )


async def inject_db_session_context(db: AsyncSession = Depends(get_db)):
    """Bind the request-scoped database session.

    Mounted on the API routers in core/registry.py, NOT on the FastAPI app — as
    an app-level dependency it opened a pooled connection for every /health
    liveness probe.
    """
    token = db_session_ctx.set(db)
    try:
        yield
    finally:
        db_session_ctx.reset(token)
