# app/modules/auth/schemas.py
from pydantic import BaseModel, EmailStr, Field


class AdminRegisterSchema(BaseModel):
    """Payload for self-service admin registration.

    `is_superuser` is intentionally NOT exposed here. Privilege elevation must
    happen through a separate endpoint protected by a superadmin dependency.
    """

    email: EmailStr
    password: str = Field(..., min_length=8, max_length=72, examples=["SecureAdminPass123!"])


class AdminLoginSchema(BaseModel):
    """Payload for authenticating an admin with email and password."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=72)


class AdminTokenOutSchema(BaseModel):
    """JWT token pair response for a successfully authenticated admin."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class TokenRefreshSchema(BaseModel):
    """Payload for exchanging a refresh token for a new access token."""

    refresh_token: str


class PasswordChangeSchema(BaseModel):
    """Payload for changing the admin's own password."""

    current_password: str = Field(..., min_length=1, max_length=72)
    new_password: str = Field(..., min_length=8, max_length=72)
