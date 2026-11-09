"""atomic(): the transaction boundary every service write goes through."""

import pytest
from sqlalchemy import select

from app.database import atomic
from app.modules.auth.models import Auth


def _auth(email: str) -> Auth:
    return Auth(email=email, password="x")


async def test_read_then_write_commits(db_session):
    """The bug it exists for: a read autobegins, and db.begin() then raised."""
    await db_session.execute(select(Auth))
    async with atomic(db_session):
        db_session.add(_auth("a@example.com"))

    rows = (await db_session.execute(select(Auth))).scalars().all()
    assert [r.email for r in rows] == ["a@example.com"]


async def test_error_rolls_back(db_session):
    with pytest.raises(ValueError):
        async with atomic(db_session):
            db_session.add(_auth("b@example.com"))
            await db_session.flush()
            raise ValueError("boom")

    assert (await db_session.execute(select(Auth))).scalars().all() == []


async def test_nesting_is_refused(db_session):
    async with atomic(db_session):
        with pytest.raises(RuntimeError, match="does not nest"):
            async with atomic(db_session):
                pass
