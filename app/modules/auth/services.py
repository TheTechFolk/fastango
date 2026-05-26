# app/modules/auth/services.py
from typing import Optional, Tuple

from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from app.database import get_db_session
from app.modules.auth.constants import (
    ACCOUNT_INACTIVE_MSG,
    ADMIN_LOGIN_SUCCESS_MSG,
    ADMIN_REGISTER_SUCCESS_MSG,
    EMAIL_TAKEN_MSG,
    INVALID_CREDENTIALS_MSG,
)
from app.modules.auth.models import AdminAuth
from app.modules.auth.repositories import AdminAuthRepository
from app.modules.auth.schemas import AdminLoginSchema, AdminRegisterSchema


class AdminAuthService:
    """Business logic for admin authentication flows."""

    async def register(
        self, data: AdminRegisterSchema
    ) -> Tuple[Optional[dict], str]:
        """
        Register a new admin account.

        New accounts are ALWAYS created with `is_superuser=False`. Elevation
        happens through a separate superadmin-guarded endpoint.
        """
        db = get_db_session()
        async with db.begin():
            if await AdminAuthRepository.get_by_email(db, data.email):
                return None, EMAIL_TAKEN_MSG

            admin = AdminAuth(
                email=data.email,
                password_hash=hash_password(data.password),
                is_superuser=False,
            )
            await AdminAuthRepository.create(db, admin)

        return self._build_tokens(admin), ADMIN_REGISTER_SUCCESS_MSG

    async def login(
        self, data: AdminLoginSchema
    ) -> Tuple[Optional[dict], str]:
        """
        Authenticate an admin user.

        Returns the same generic error for both "user not found" and "wrong
        password" so the response cannot be used for account enumeration.
        """
        db = get_db_session()
        admin = await AdminAuthRepository.get_by_email(db, data.email)
        if not admin:
            return None, INVALID_CREDENTIALS_MSG
        if not admin.is_active:
            return None, ACCOUNT_INACTIVE_MSG
        if not verify_password(data.password, admin.password_hash):
            return None, INVALID_CREDENTIALS_MSG

        return self._build_tokens(admin), ADMIN_LOGIN_SUCCESS_MSG

    def _build_tokens(self, admin: AdminAuth) -> dict:
        """Generate an access + refresh token pair for the given admin record."""
        return {
            "access_token": create_access_token(
                subject=admin.admin_code, role="admin"
            ),
            "refresh_token": create_refresh_token(subject=admin.admin_code),
            "token_type": "bearer",
        }
