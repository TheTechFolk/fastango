# app/modules/sample/schemas.py
from pydantic import BaseModel


class SampleOutSchema(BaseModel):
    """Response shape for the sample endpoint."""

    message: str

    model_config = {"from_attributes": True}
