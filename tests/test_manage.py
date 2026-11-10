"""manage.py createsuperuser — the one command with logic of its own."""

import pytest
from sqlalchemy import select

from app.core.constants import RoleType
from app.modules.auth.models import Auth
from app.modules.auth.utils import verify_password
from manage import create_superuser


async def test_createsuperuser_makes_a_hashed_admin(db_session):
    await create_superuser(db_session, " Admin@Example.com ", "SuperSecretPassword123")

    record = (await db_session.execute(select(Auth))).scalars().one()
    assert record.email == "admin@example.com"
    assert record.role == RoleType.ADMIN.value
    assert verify_password("SuperSecretPassword123", record.password)


async def test_createsuperuser_enforces_the_register_password_policy(db_session):
    with pytest.raises(ValueError):
        await create_superuser(db_session, "admin@example.com", "short")


async def test_createsuperuser_refuses_a_taken_email(db_session):
    await create_superuser(db_session, "admin@example.com", "SuperSecretPassword123")
    with pytest.raises(ValueError, match="already exists"):
        await create_superuser(db_session, "admin@example.com", "SuperSecretPassword123")
