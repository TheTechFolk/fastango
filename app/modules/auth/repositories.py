# app/modules/auth/repositories.py
import uuid
from typing import Optional

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AdminAuth


class AdminAuthRepository:
    """
    Data-access layer for AdminAuth records.
    Relocated from app/modules/admin/auth/repositories.py to the shared
    top-level auth module.
    """

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Optional[AdminAuth]:
        """Fetch an admin auth record by email address."""
        result = await db.execute(select(AdminAuth).where(AdminAuth.email == email))
        return result.scalars().first()

    @staticmethod
    async def get_by_admin_code(
        db: AsyncSession, admin_code: uuid.UUID
    ) -> Optional[AdminAuth]:
        """Fetch an admin auth record by admin_code UUID."""
        result = await db.execute(
            select(AdminAuth).where(AdminAuth.admin_code == admin_code)
        )
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, admin: AdminAuth) -> AdminAuth:
        """Persist a new AdminAuth record."""
        db.add(admin)
        await db.flush()
        await db.refresh(admin)
        return admin
