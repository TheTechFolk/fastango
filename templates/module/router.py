# app/modules/sample/router.py
from fastapi import APIRouter

from app.core.decorators import api_response
from app.core.responses import APIResponse
from app.modules.sample.schemas import SampleOutSchema
from app.modules.sample.services import SampleService

# No prefix/tags here — apps.py owns those, and it also decides whether this
# mounts under /private/api/v1 (default) or /public/api/v1.
router = APIRouter()


@router.get("", response_model=APIResponse[SampleOutSchema])
@api_response()
async def get_sample():
    """Example endpoint: return (data, message); raise an AppException to fail."""
    return await SampleService.get_sample_data()
