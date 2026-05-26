# app/modules/profile/router.py
import uuid

from fastapi import APIRouter, Depends, HTTPException, status

from app.core.responses import APIResponse, success_response
from app.core.security import get_current_user_code
from app.modules.profile.constants import PROFILE_RETRIEVED_MSG
from app.modules.profile.schemas import ProfileOutSchema
from app.modules.profile.services import ProfileService

router = APIRouter()


@router.get("", response_model=APIResponse[ProfileOutSchema])
async def get_profile(
    user_code: uuid.UUID = Depends(get_current_user_code),
):
    """Retrieve profile information for the authenticated user."""
    service = ProfileService()
    data, error = await service.get_user_profile(user_code)
    if error:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=error,
        )
    return success_response(data=data, message=PROFILE_RETRIEVED_MSG)
