# app/modules/sample/router.py
from fastapi import APIRouter

from app.core.responses import APIResponse, success_response
from app.modules.sample.schemas import SampleOutSchema
from app.modules.sample.services import SampleService

# No prefix/tags here — they are owned by apps.py.
router = APIRouter()


@router.get("", response_model=APIResponse[SampleOutSchema])
async def get_sample():
    """Example endpoint. Replace with your module's real routes."""
    data, msg = await SampleService.get_sample_data()
    return success_response(data=data, message=msg)
