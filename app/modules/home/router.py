# app/modules/home/router.py
import uuid
from fastapi import APIRouter, Depends

from app.core.responses import APIResponse, success_response
from app.core.security import get_current_user_code
from app.modules.home.schemas import HomeDataOutSchema
from app.modules.home.services import HomeService

router = APIRouter()


@router.get("", response_model=APIResponse[HomeDataOutSchema])
async def get_home(user_code: uuid.UUID = Depends(get_current_user_code)):
    """A simple home welcome endpoint for logged in users."""
    data, msg = await HomeService.get_home_data(user_code)
    return success_response(data=data, message=msg)
