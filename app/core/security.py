# app/core/security.py
"""
Credential verification — the half of auth that runs on every request.

Signing tokens and hashing passwords happen only at register and login, so they
live in app/modules/auth/utils.py. Decoding happens on every private request,
which is why it stays here: app/middleware.py needs it, and core importing from
a module would invert the dependency the module registry rests on — delete the
auth module and the whole app would stop booting rather than just that module.

    auth/utils.py     issues credentials  (hash, sign)
    core/security.py  verifies them       (decode, identify)
"""

import uuid
from collections.abc import Callable

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer
from jwt.exceptions import InvalidTokenError

from app.config import settings
from app.core.constants import ACCESS_TOKEN_TYPE, FORBIDDEN_MSG, RoleType

# ── Bearer Token Scheme ────────────────────────────────────────────────────────
# Attached to the private router so Swagger renders an Authorize button and the
# docs can actually exercise a protected endpoint. auto_error=False because
# rejection is the middleware's job — this scheme only describes the header.
bearer_scheme = HTTPBearer(auto_error=False)

# The algorithms a token may be signed with, hardcoded. Taking this list from
# settings means JWT_ALGORITHM=none makes the decoder accept unsigned tokens;
# only the *signing* side has any reason to be configurable.
ACCEPTED_ALGORITHMS = ["HS256", "HS384", "HS512"]

# Claims a token must carry. PyJWT validates `exp` only when it is present, so
# without this a token minted with no expiry is valid forever.
REQUIRED_CLAIMS = ["exp", "iat", "sub", "type"]


# ── JWT Decode ─────────────────────────────────────────────────────────────────
def decode_token(token: str, expected_type: str = ACCESS_TOKEN_TYPE) -> dict:
    """Decode and validate a JWT, asserting it matches the expected token type.

    Without the type check, a long-lived refresh token would be accepted as an
    access token if sent in the Authorization header.
    """
    try:
        payload = jwt.decode(
            token,
            settings.SECRET_KEY,
            algorithms=ACCEPTED_ALGORITHMS,
            options={"require": REQUIRED_CLAIMS},
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
# The auth middleware has already decoded the token and rejected the request if
# it was missing or invalid, so these are cheap reads of what it stored — no
# second decode, and no second place that decides what "authenticated" means.
#
# There is deliberately no environment that waives these. The bypass this
# replaces returned a mock identity whenever APP_ENV was local/test — it shipped
# in the production image and was one env var from disabling auth entirely.
def _unauthenticated() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Not authenticated. Bearer token is missing.",
        headers={"WWW-Authenticate": "Bearer"},
    )


async def get_current_user_code(request: Request) -> uuid.UUID:
    """The authenticated caller's UUID, as taken from the access token.

    Also the private router's route-level guard: the URL-prefix check in the
    middleware is the only other thing standing between /private and the world,
    and a single mounting mistake would silently open it.
    """
    user_code = getattr(request.state, "user_code", None)
    if not user_code:
        # Only reachable if a route is public but asks who is calling.
        raise _unauthenticated()
    try:
        return uuid.UUID(str(user_code))
    except ValueError as exc:
        # A token whose `sub` is not a UUID is a bad token, not a server fault.
        raise _unauthenticated() from exc


async def get_current_user_role(request: Request) -> str:
    """The authenticated caller's role claim."""
    return getattr(request.state, "role", None) or RoleType.USER.value


def require_role(*allowed: RoleType) -> Callable:
    """Route dependency asserting the caller holds one of `allowed`.

    Note the role comes from the token, so a demotion takes effect no sooner
    than the token expires — acceptable for coarse gating, not for revocation.
    """
    permitted = {role.value for role in allowed}

    async def guard(role: str = Depends(get_current_user_role)) -> str:
        if role not in permitted:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=FORBIDDEN_MSG)
        return role

    return guard
