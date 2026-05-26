# app/modules/home/services.py
import uuid
from typing import Tuple

from app.modules.home.constants import HOME_RETRIEVED_MSG


class HomeService:
    @staticmethod
    async def get_home_data(user_code: uuid.UUID) -> Tuple[dict, str]:
        """Fetch general-purpose home/dashboard data for any authenticated user."""
        return {
            "welcome_message": "Welcome to the Fastango platform!",
            "user_code": str(user_code),
        }, HOME_RETRIEVED_MSG
