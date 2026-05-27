# app/core/security.py
import uuid
from datetime import UTC, datetime, timedelta

import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.config import settings

# ── Bearer Token Scheme ────────────────────────────────────────────────────────
bearer_scheme = HTTPBearer(auto_error=False)

_DEV_ENVS = ("local", "test", "testing")


# ── Password Hashing ──────────────────────────────────────────────────────────
def hash_password(plain_password: str) -> str:
    """
    Hash a plain-text password using bcrypt.

    Note: bcrypt silently truncates inputs longer than 72 bytes. Enforce a
    length cap at the schema layer or pre-hash if you need longer passwords.
    """
    return bcrypt.hashpw(plain_password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except ValueError:
        # Malformed hash → treat as failed verification, never raise.
        return False


# ── JWT Encode ─────────────────────────────────────────────────────────────────
def create_access_token(
    subject: str | uuid.UUID,
    role: str = "user",
    expires_delta: timedelta | None = None,
) -> str:
    """Generate a short-lived signed JWT access token."""
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "role": role,
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "access",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | uuid.UUID) -> str:
    """Generate a long-lived signed JWT refresh token."""
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": "refresh",
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


# ── JWT Decode ─────────────────────────────────────────────────────────────────
def decode_token(token: str, expected_type: str = "access") -> dict:
    """
    Decode and validate a JWT, asserting it matches the expected token type.

    Without the type check, a long-lived refresh token would be accepted as an
    access token if sent in the Authorization header.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token.",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    if payload.get("type") != expected_type:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload


# ── Shared Auth Dependencies ───────────────────────────────────────────────────
async def get_current_user_code(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> uuid.UUID:
    """
    FastAPI dependency that extracts the authenticated user's UUID from the
    Bearer JWT token. In local/test environments only, falls back to a mock
    UUID when no token is supplied.
    """
    if credentials is None:
        if settings.APP_ENV in _DEV_ENVS:
            return uuid.UUID("3fa85f64-5717-4562-b3fc-2c963f66afa6")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Bearer token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = decode_token(credentials.credentials, expected_type="access")
    user_code_str: str | None = payload.get("sub")
    if not user_code_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token subject missing.",
        )
    return uuid.UUID(user_code_str)


async def get_current_user_role(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
) -> str:
    """Extract the role claim from the JWT access token."""
    if credentials is None:
        if settings.APP_ENV in _DEV_ENVS:
            return "user"
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated. Bearer token is missing.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    payload = decode_token(credentials.credentials, expected_type="access")
    return payload.get("role", "user")
