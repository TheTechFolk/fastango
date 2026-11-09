#!/usr/bin/env python
"""
Fastango — management commands, for hands used to `python manage.py`.

    python manage.py createsuperuser [--email EMAIL]
    python manage.py shell
    python manage.py makemigrations [-m MESSAGE]
    python manage.py migrate [TARGET]

Thin on purpose: migrations are Alembic underneath, and `shell` is Python's own
asyncio REPL. Nothing here runs inside the server process.
"""

import argparse
import asyncio
import getpass
import os
import subprocess
import sys

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.constants import RoleType
from app.modules.auth.models import Auth
from app.modules.auth.repositories import AuthRepository
from app.modules.auth.schemas import RegisterSchema
from app.modules.auth.utils import ahash_password

# Set only for the REPL `shell` spawns, which runs this same file as its
# PYTHONSTARTUP — see _preload_shell().
SHELL_FLAG = "FASTANGO_SHELL"


# ── createsuperuser ───────────────────────────────────────────────────────────
async def create_superuser(db: AsyncSession, email: str, password: str) -> Auth:
    """Create an ADMIN account. Raises ValueError on a bad or taken email.

    Validated through RegisterSchema, so an admin gets the same email
    normalization and password policy as /register — a CLI that accepted
    weaker passwords would be a back door to the most privileged accounts.
    """
    try:
        data = RegisterSchema(email=email, password=password)
    except ValidationError as exc:
        raise ValueError("; ".join(err["msg"] for err in exc.errors())) from None

    password_hash = await ahash_password(data.password)
    async with db.begin():
        if await AuthRepository.get_by_email(db, data.email):
            raise ValueError(f"An account with email {data.email} already exists.")
        record = Auth(email=data.email, password=password_hash, role=RoleType.ADMIN.value)
        return await AuthRepository.create(db, record)


def _createsuperuser(args: argparse.Namespace) -> None:
    from app.database import async_session_factory, engine

    email = args.email or input("Email: ")
    # Like DJANGO_SUPERUSER_PASSWORD: lets scripts and containers run this
    # non-interactively, without the password landing in shell history.
    password = os.environ.get("SUPERUSER_PASSWORD")
    if password is None:
        password = getpass.getpass("Password: ")
        if password != getpass.getpass("Password (again): "):
            sys.exit("Error: passwords didn't match.")

    async def run() -> Auth:
        try:
            async with async_session_factory() as db:
                return await create_superuser(db, email, password)
        finally:
            await engine.dispose()

    try:
        record = asyncio.run(run())
    except ValueError as exc:
        sys.exit(f"Error: {exc}")
    print(f"Superuser {record.email} created.")


# ── shell ─────────────────────────────────────────────────────────────────────
def _shell(_: argparse.Namespace) -> None:
    """Python's asyncio REPL (top-level `await` works) with the app preloaded."""
    if sys.version_info < (3, 13):
        # 3.12's asyncio REPL ignores PYTHONSTARTUP, so it would open with
        # nothing loaded. Fail loudly rather than hand over an empty shell.
        sys.exit("manage.py shell needs Python 3.13+.")
    env = {**os.environ, SHELL_FLAG: "1", "PYTHONSTARTUP": os.path.abspath(__file__)}  # type: ignore[unreachable]  # mypy targets 3.12
    sys.exit(subprocess.call([sys.executable, "-m", "asyncio"], env=env))


def _preload_shell() -> None:
    """Runs inside the REPL: put settings, a session and every model in scope."""
    from sqlalchemy import select

    from app.config import settings
    from app.core.registry import import_all_models
    from app.database import Base, async_session_factory

    async def fetch(statement):
        """Run a select in its own short session and return the rows."""
        async with async_session_factory() as session:
            return (await session.execute(statement)).scalars().all()

    # No long-lived session in scope: one left open holds a pooled connection
    # until the interpreter dies, and asyncpg can't close it that late.
    import_all_models()
    models = {m.class_.__name__: m.class_ for m in Base.registry.mappers}
    globals().update(
        models, settings=settings, select=select, Session=async_session_factory, fetch=fetch
    )
    print("Preloaded: settings, select, Session, fetch, " + ", ".join(sorted(models)))
    print("Read:  await fetch(select(Auth))")
    print("Write: async with Session() as db, db.begin(): db.add(...)")


# ── migrations ────────────────────────────────────────────────────────────────
def _alembic_config():
    from alembic.config import Config

    return Config(os.path.join(os.path.dirname(os.path.abspath(__file__)), "alembic.ini"))


def _makemigrations(args: argparse.Namespace) -> None:
    from alembic import command

    command.revision(_alembic_config(), message=args.message, autogenerate=True)


def _migrate(args: argparse.Namespace) -> None:
    from alembic import command

    command.upgrade(_alembic_config(), args.target)


def main() -> None:
    parser = argparse.ArgumentParser(prog="manage.py", description="Fastango management commands.")
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("createsuperuser", help="create an ADMIN account")
    p.add_argument("--email")
    p.set_defaults(func=_createsuperuser)

    p = sub.add_parser("shell", help="async Python shell with the app loaded")
    p.set_defaults(func=_shell)

    p = sub.add_parser("makemigrations", help="autogenerate an Alembic revision")
    p.add_argument("-m", "--message", default="auto")
    p.set_defaults(func=_makemigrations)

    p = sub.add_parser("migrate", help="apply migrations (default: head)")
    p.add_argument("target", nargs="?", default="head")
    p.set_defaults(func=_migrate)

    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    if os.environ.pop(SHELL_FLAG, None):
        _preload_shell()
    else:
        main()
