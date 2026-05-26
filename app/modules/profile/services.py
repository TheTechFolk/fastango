# app/modules/profile/services.py
import uuid
from typing import Optional, Tuple
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db_session
from app.modules.profile.constants import PROFILE_NOT_FOUND_MSG, PROFILE_RETRIEVED_MSG
from app.modules.profile.repositories import ProfileRepository


class ProfileService:
    async def get_user_profile(self, user_code: uuid.UUID) -> Tuple[Optional[dict], Optional[str]]:
        """Orchestrate profile data retrieval for the authenticated user."""
        db = get_db_session()
        admin = await ProfileRepository.get_profile_by_code(db, user_code)
        if not admin:
            return None, PROFILE_NOT_FOUND_MSG

        return {
            "admin_code": admin.admin_code,
            "email": admin.email,
            "is_superuser": admin.is_superuser,
            "is_active": admin.is_active,
        }, None

