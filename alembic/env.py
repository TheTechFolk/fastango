# alembic/env.py
"""
Alembic migration environment for Fastango.
Configured for async SQLAlchemy.
"""

import asyncio
from logging.config import fileConfig

from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context
from app.config import settings
from app.core.registry import import_all_models
from app.database import Base

# Import every module's models so autogenerate sees the same tables the running
# app does. This is the same call app boot makes — one source of truth.
import_all_models()

config = context.config
# The URL comes from settings, never from alembic.ini — one place to configure,
# and no credentials committed to the repo.
config.set_main_option("sqlalchemy.url", settings.DATABASE_URL)

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode (generate SQL without a DB connection)."""
    context.configure(
        url=config.get_main_option("sqlalchemy.url"),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        # Without this, `alembic check` and autogenerate miss column type
        # changes entirely — the drift the CI job exists to catch.
        compare_type=True,
        compare_server_default=True,
        # SQLite cannot ALTER most things; batch mode rewrites the table.
        # Harmless on Postgres, and it keeps a local sqlite run working.
        render_as_batch=settings.DATABASE_URL.startswith("sqlite"),
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    """Run migrations in 'online' mode using an async engine."""
    connectable = create_async_engine(settings.DATABASE_URL, echo=False)
    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
