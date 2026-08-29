# app/modules/auth/utils.py
"""
Credential minting — the half of auth that only the auth module performs.

Hashing a password and signing a token happen exactly once each, at register
and login. Verifying them happens on every request, which is why the decode
side stays in app/core/security.py: the auth middleware needs it, and core
cannot import from a module without inverting the dependency the whole registry
rests on.

The split reads as: **auth issues credentials, core verifies them.**
"""

import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import anyio.to_thread
import bcrypt
import jwt

from app.config import settings
from app.core.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE, RoleType


# ── Password Hashing ──────────────────────────────────────────────────────────
# bcrypt at cost 12 is ~300ms of pure CPU by design. On the event loop that is
# 300ms during which the worker serves nobody, so every call below goes to a
# thread. The sync functions stay available for the rare non-async caller.
def hash_password(plain_password: str) -> str:
    """Hash a plain-text password using bcrypt. Blocking — prefer ahash_password.

    bcrypt silently truncates input past 72 bytes, so the cap lives on
    NewPasswordField in modules/common/schemas.py — without it, everything
    after the 72nd byte would count for nothing.

    The cost factor is explicit rather than the library default, which drifts
    between releases; a security parameter that changes when you upgrade a
    dependency is not one you have chosen.
    """
    salt = bcrypt.gensalt(rounds=settings.BCRYPT_ROUNDS)
    return bcrypt.hashpw(plain_password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plain-text password against its bcrypt hash. Blocking."""
    try:
        return bcrypt.checkpw(plain_password.encode("utf-8"), hashed_password.encode("utf-8"))
    except (ValueError, TypeError, AttributeError):
        # Malformed or missing hash → a failed verification, never a 500.
        return False


async def ahash_password(plain_password: str) -> str:
    """hash_password, off the event loop."""
    return await anyio.to_thread.run_sync(hash_password, plain_password)


async def averify_password(plain_password: str, hashed_password: str) -> bool:
    """verify_password, off the event loop."""
    return await anyio.to_thread.run_sync(verify_password, plain_password, hashed_password)


@lru_cache(maxsize=1)
def dummy_hash() -> str:
    """A real hash of a value nothing can match.

    Login verifies against this when the email is unknown, so an unknown account
    costs the same bcrypt work as a known one. Without it the two answer in ~2ms
    and ~300ms respectively, which is an account-enumeration oracle regardless
    of how identical the message is.

    Computed on first use, not at import: as a module-level constant this cost
    ~300ms of bcrypt on every import of the package, including Alembic and test
    collection.
    """
    return hash_password(uuid.uuid4().hex)


# ── JWT Signing ───────────────────────────────────────────────────────────────
def create_access_token(
    subject: str | uuid.UUID,
    role: str = RoleType.USER.value,
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
        "type": ACCESS_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token(subject: str | uuid.UUID) -> str:
    """Generate a long-lived signed JWT refresh token.

    Carries no `role` claim on purpose: roles can change between issue and
    refresh, so the value is re-read from the record rather than replayed.
    """
    expire = datetime.now(UTC) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    payload = {
        "sub": str(subject),
        "exp": expire,
        "iat": datetime.now(UTC),
        "type": REFRESH_TOKEN_TYPE,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
