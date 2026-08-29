# app/modules/auth/schemas.py
import uuid

from pydantic import BaseModel, ConfigDict

from app.core.responses import APIResponse
from app.modules.common.schemas import EmailField, ExistingPasswordField, NewPasswordField


class RegisterSchema(BaseModel):
    """Payload for self-service registration.

    `role` is intentionally NOT exposed. Privilege elevation must happen through
    a separate endpoint protected by an admin dependency.
    """

    email: EmailField
    password: NewPasswordField


class LoginSchema(BaseModel):
    """Payload for authenticating with email and password."""

    email: EmailField
    password: ExistingPasswordField


class RefreshSchema(BaseModel):
    """Payload for exchanging a refresh token for a new token pair."""

    refresh_token: str


class TokenOutSchema(BaseModel):
    """JWT token pair for a successfully authenticated account."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class MeOutSchema(BaseModel):
    """The caller's own account."""

    model_config = ConfigDict(from_attributes=True)

    code: uuid.UUID
    email: str
    role: str
    is_active: bool


# Envelope aliases, so routers name one type instead of nesting generics inline.
TokenResponse = APIResponse[TokenOutSchema]
MeResponse = APIResponse[MeOutSchema]
