# app/modules/profile/schemas.py
import uuid

from pydantic import BaseModel, EmailStr


class ProfileOutSchema(BaseModel):
    admin_code: uuid.UUID
    email: EmailStr
    is_superuser: bool
    is_active: bool

    model_config = {"from_attributes": True}
