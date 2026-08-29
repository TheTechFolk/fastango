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
    """Example endpoint. Replace with your module's real routes.

    Handlers stay one line: return `(data, message)` and @api_response wraps it
    in the {error, message, data} envelope. Raise an AppException to fail — it
    carries its own status code, so no handler writes one.

    Do NOT decorate endpoints that return a Response subclass (FileResponse,
    StreamingResponse); their body is already final.
    """
    return await SampleService.get_sample_data()
