# app/modules/profile/repositories.py
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AdminAuth
from app.modules.auth.repositories import AdminAuthRepository


class ProfileRepository:
    @staticmethod
    async def get_profile_by_code(db: AsyncSession, user_code: uuid.UUID) -> AdminAuth | None:
        """Fetch the AdminAuth profile details based on their admin_code UUID."""
        return await AdminAuthRepository.get_by_admin_code(db, user_code)
