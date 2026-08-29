# app/modules/auth/router.py
from fastapi import APIRouter, Depends, Request, status

from app.config import settings
from app.core.decorators import api_response
from app.core.rate_limit import limiter
from app.core.security import get_current_user_code
from app.modules.auth.dependencies import registration_enabled
from app.modules.auth.schemas import (
    LoginSchema,
    MeResponse,
    RefreshSchema,
    RegisterSchema,
    TokenResponse,
)
from app.modules.auth.services import AccountService, AuthService, TokenRefreshService

# No prefix/tags here — apps.py owns those, and it also decides which of these
# mounts under /public/api/v1 and which under /private/api/v1.
public_router = APIRouter()
private_router = APIRouter()


@public_router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(registration_enabled)],
)
@limiter.limit(settings.RATE_LIMIT_REGISTER)
@api_response()
async def register(request: Request, payload: RegisterSchema):
    """Create an account and return a JWT token pair."""
    return await AuthService(payload).register()


@public_router.post("/login", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
@api_response()
async def login(request: Request, payload: LoginSchema):
    """Authenticate an account and return a JWT token pair."""
    return await AuthService(payload).login()


@public_router.post("/refresh", response_model=TokenResponse)
@limiter.limit(settings.RATE_LIMIT_LOGIN)
@api_response()
async def refresh(request: Request, payload: RefreshSchema):
    """Exchange a valid refresh token for a new token pair.

    Public because a caller with an expired access token cannot get past the
    auth middleware — that is the whole situation this endpoint exists for. The
    refresh token is the credential, and it is rate-limited like a login.
    """
    return await TokenRefreshService(payload).refresh()


@private_router.get("/me", response_model=MeResponse)
@api_response()
async def me(user_code=Depends(get_current_user_code)):
    """The authenticated caller's own account."""
    return await AccountService(user_code).me()
