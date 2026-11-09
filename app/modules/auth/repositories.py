# app/modules/auth/repositories.py
import uuid
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import Auth, RevokedToken


class AuthRepository:
    """Data access for Auth records. Never commits — services own transactions."""

    @staticmethod
    async def get_by_email(db: AsyncSession, email: str) -> Auth | None:
        """Fetch an auth record by email address."""
        result = await db.execute(select(Auth).where(Auth.email == email))
        return result.scalars().first()

    @staticmethod
    async def get_by_code(db: AsyncSession, code: uuid.UUID) -> Auth | None:
        """Fetch an auth record by its public code."""
        result = await db.execute(select(Auth).where(Auth.code == code))
        return result.scalars().first()

    @staticmethod
    async def create(db: AsyncSession, record: Auth) -> Auth:
        """Persist a new auth record within the caller's transaction."""
        db.add(record)
        await db.flush()
        await db.refresh(record)
        return record


class RevokedTokenRepository:
    """Revoked refresh-token ids. Never commits — services own transactions."""

    @staticmethod
    async def add(db: AsyncSession, jti: str, expires_at: datetime) -> None:
        """Revoke `jti`. Raises IntegrityError if it was already revoked.

        Insert-as-check, deliberately: a separate "is it revoked?" select would
        let two concurrent requests both see "no" and both redeem the token.
        """
        db.add(RevokedToken(jti=jti, expires_at=expires_at))
        await db.flush()
