# app/modules/auth/router.py
from fastapi import APIRouter, HTTPException, Request, status

from app.config import settings
from app.core.rate_limit import limiter
from app.core.responses import APIResponse, success_response
from app.modules.auth.schemas import (
    AdminLoginSchema,
    AdminRegisterSchema,
    AdminTokenOutSchema,
)
from app.modules.auth.services import AdminAuthService

router = APIRouter()


@router.post(
    "/register",
    response_model=APIResponse[AdminTokenOutSchema],
    status_code=status.HTTP_201_CREATED,
    summary="Register a new user account",
)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
async def register(
    request: Request,
    payload: AdminRegisterSchema,
):
    """
    Create a new user account and return a JWT token pair.

    New accounts are always created as non-superuser. Use a separate
    superadmin-protected endpoint to elevate privileges.
    """
    service = AdminAuthService()
    data, msg = await service.register(payload)
    if data is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
    return success_response(data=data, message=msg)


@router.post(
    "/login",
    response_model=APIResponse[AdminTokenOutSchema],
    summary="User login",
)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
async def login(
    request: Request,
    payload: AdminLoginSchema,
):
    """Validate user credentials and return a JWT access + refresh token pair."""

    service = AdminAuthService()
    data, msg = await service.login(payload)
    if data is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=msg)
    return success_response(data=data, message=msg)
