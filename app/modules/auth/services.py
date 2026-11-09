# app/modules/auth/services.py
import uuid
from datetime import UTC, datetime

from sqlalchemy.exc import IntegrityError

from app.core.constants import REFRESH_TOKEN_TYPE, RoleType
from app.core.exceptions import UnauthorizedException, ValidationException
from app.core.security import decode_token
from app.database import get_db_session
from app.modules.auth.constants import (
    EMAIL_TAKEN_MSG,
    INVALID_CREDENTIALS_MSG,
    INVALID_REFRESH_MSG,
    LOGIN_SUCCESS_MSG,
    LOGOUT_SUCCESS_MSG,
    ME_SUCCESS_MSG,
    REFRESH_SUCCESS_MSG,
    REGISTER_SUCCESS_MSG,
)
from app.modules.auth.models import Auth
from app.modules.auth.repositories import AuthRepository, RevokedTokenRepository
from app.modules.auth.schemas import LoginSchema, MeOutSchema, RefreshSchema, RegisterSchema
from app.modules.auth.utils import (
    ahash_password,
    averify_password,
    create_access_token,
    create_refresh_token,
    dummy_hash,
)


class AuthService:
    """Registration and login. Returns (data, message); raises on failure.

    One instance is one request: the credentials come in through `__init__` and
    the record either method resolves is put on `self`, so `_build_tokens()`
    reads both rather than being handed either.
    """

    def __init__(self, data: RegisterSchema | LoginSchema) -> None:
        self.data = data
        self.record: Auth | None = None

    async def register(self) -> tuple[dict, str]:
        """Create an account and return a fresh token pair."""
        db = get_db_session()
        data = self.data

        # Hashed before the transaction opens, not inside it. bcrypt is ~300ms
        # of CPU; doing it under `db.begin()` holds a pooled connection and a
        # row lock for that whole time, for no reason — the hash depends on
        # nothing the transaction reads.
        password_hash = await ahash_password(data.password)

        try:
            # get_db() does not auto-commit, and uncommitted writes raise at
            # request end — the transaction boundary has to be explicit.
            async with db.begin():
                if await AuthRepository.get_by_email(db, data.email):
                    raise ValidationException(EMAIL_TAKEN_MSG)

                self.record = Auth(
                    email=data.email,
                    password=password_hash,
                    # Never read from the request body. This single line is the
                    # difference between a signup form and a privilege
                    # escalation.
                    role=RoleType.USER.value,
                )
                await AuthRepository.create(db, self.record)
        except IntegrityError:
            # The lookup above is not atomic: two concurrent signups for one
            # email both pass it and the second trips the unique constraint.
            # Unhandled, that request would 500 instead of returning a clean
            # 400 with the same generic message.
            raise ValidationException(EMAIL_TAKEN_MSG) from None

        return self._build_tokens(), REGISTER_SUCCESS_MSG

    async def login(self) -> tuple[dict, str]:
        """Verify credentials and return a fresh token pair.

        Identical response *and* identical cost for every failure, so the
        endpoint cannot be used to enumerate registered accounts:

        - An unknown email still pays for a bcrypt verification, against a dummy
          hash. Short-circuiting on `not self.record` makes an unknown email
          answer in ~2ms and a known one in ~300ms — the message is identical
          and the timing is not.
        - A disabled account answers with the credentials message rather than
          its own. A distinct message tells anyone who ever knew the password
          that the account still exists.
        """
        db = get_db_session()
        self.record = await AuthRepository.get_by_email(db, self.data.email)

        stored_hash = self.record.password if self.record else dummy_hash()
        password_ok = await averify_password(self.data.password, stored_hash)

        if not self.record or not password_ok or not self.record.is_active:
            raise UnauthorizedException(INVALID_CREDENTIALS_MSG)

        return self._build_tokens(), LOGIN_SUCCESS_MSG

    def _build_tokens(self) -> dict:
        """Access + refresh pair for the record this request resolved.

        Reached only after register() created a record or login() verified one,
        so `self.record` is set — asserted rather than assumed, because the
        alternative is an AttributeError on None at token-minting time.
        """
        record = self.record
        if record is None:
            raise RuntimeError("_build_tokens() called before a record was resolved.")
        return {
            "access_token": create_access_token(subject=record.code, role=record.role),
            "refresh_token": create_refresh_token(subject=record.code),
            "token_type": "bearer",
        }


def _decode_refresh(token: str) -> dict:
    """Decode a refresh token and insist it is revocable.

    Raises 401 on a bad signature, a missing claim, expiry, or an access token
    presented in a refresh token's place. A token minted before `jti` existed
    cannot be revoked, so it is refused rather than honored forever.
    """
    claims = decode_token(token, REFRESH_TOKEN_TYPE)
    if not claims.get("jti"):
        raise UnauthorizedException(INVALID_REFRESH_MSG)
    return claims


async def _revoke(claims: dict) -> None:
    """Revoke a decoded refresh token. Raises IntegrityError if already revoked."""
    await RevokedTokenRepository.add(
        get_db_session(),
        jti=str(claims["jti"]),
        expires_at=datetime.fromtimestamp(claims["exp"], UTC),
    )


class TokenRefreshService:
    """Redeem a refresh token for a fresh pair.

    Without this, every register and login hands out a 7-day refresh token that
    no endpoint would accept — a long-lived credential with all of the exposure
    and none of the function.

    The role is re-read from the record rather than replayed from the token,
    which is why `create_refresh_token` carries no role claim: a demotion takes
    effect at the next refresh instead of being carried forward indefinitely.
    """

    def __init__(self, payload: RefreshSchema) -> None:
        self.payload = payload

    async def refresh(self) -> tuple[dict, str]:
        """Rotate: the presented token is revoked as the new pair is issued.

        Without rotation logout would be hollow — every refresh hands out a new
        token while the old one stays redeemable for its full 7 days, so
        revoking the latest one would leave its predecessors working.
        """
        claims = _decode_refresh(self.payload.refresh_token)

        try:
            code = uuid.UUID(str(claims.get("sub")))
        except ValueError as exc:
            raise UnauthorizedException(INVALID_REFRESH_MSG) from exc

        db = get_db_session()
        try:
            async with db.begin():
                record = await AuthRepository.get_by_code(db, code)
                # A token can outlive the account it names. Deactivation is only
                # checked at login, so this is where a disabled account stops
                # renewing.
                if record is None or not record.is_active:
                    raise UnauthorizedException(INVALID_REFRESH_MSG)
                await _revoke(claims)
        except IntegrityError:
            # Already revoked: logged out, or already rotated. A reused
            # refresh token is exactly what a stolen one looks like.
            raise UnauthorizedException(INVALID_REFRESH_MSG) from None

        return {
            "access_token": create_access_token(subject=record.code, role=record.role),
            "refresh_token": create_refresh_token(subject=record.code),
            "token_type": "bearer",
        }, REFRESH_SUCCESS_MSG


class LogoutService:
    """Revoke a refresh token so it can never be redeemed again.

    The access token is not touched: it is never looked up, so it lives out its
    short lifetime. That keeps every private request I/O-free; the client
    drops it on logout anyway.
    """

    def __init__(self, payload: RefreshSchema) -> None:
        self.payload = payload

    async def logout(self) -> tuple[None, str]:
        claims = _decode_refresh(self.payload.refresh_token)
        db = get_db_session()
        try:
            async with db.begin():
                await _revoke(claims)
        except IntegrityError:
            # Logging out twice is still logged out.
            pass
        return None, LOGOUT_SUCCESS_MSG


class AccountService:
    """The caller's own account, resolved from the token the middleware read."""

    def __init__(self, user_code: uuid.UUID) -> None:
        self.user_code = user_code

    async def me(self) -> tuple[MeOutSchema, str]:
        record = await AuthRepository.get_by_code(get_db_session(), self.user_code)
        if record is None or not record.is_active:
            # The token is valid but the account behind it is not.
            raise UnauthorizedException(INVALID_CREDENTIALS_MSG)
        return MeOutSchema.model_validate(record), ME_SUCCESS_MSG
