"""IntegrityError -> 409, with a message that matches what actually failed."""

import pytest
from sqlalchemy.exc import IntegrityError

from app.core.constants import ALREADY_EXISTS_MSG, CONFLICT_MSG
from app.core.registry import PRIVATE_ROOT
from app.exceptions import _is_unique_violation
from app.modules.auth.models import Auth


async def test_duplicate_key_is_recognised_as_unique(db_session):
    db_session.add(Auth(email="dup@example.com", password="x"))
    await db_session.commit()

    db_session.add(Auth(email="dup@example.com", password="x"))
    with pytest.raises(IntegrityError) as excinfo:
        await db_session.commit()
    await db_session.rollback()

    assert _is_unique_violation(excinfo.value)


async def test_foreign_key_failure_does_not_claim_already_exists(client):
    """The `client` fixture's identity was never registered, so a note it
    creates points at an owner that does not exist. That is a conflict, and
    "Resource already exists" would be the wrong thing to tell the caller."""
    resp = await client.post(f"{PRIVATE_ROOT}/notes", json={"title": "orphan"})
    assert resp.status_code == 409
    assert resp.json()["message"] == CONFLICT_MSG != ALREADY_EXISTS_MSG
