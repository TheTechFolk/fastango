"""Token decoding: algorithms, required claims, type segregation."""

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from fastapi import HTTPException

from app.config import settings
from app.core.constants import ACCESS_TOKEN_TYPE, REFRESH_TOKEN_TYPE
from app.core.security import ACCEPTED_ALGORITHMS, decode_token
from app.modules.auth.utils import create_access_token, create_refresh_token

SUBJECT = "3fa85f64-5717-4562-b3fc-2c963f66afa6"


def test_access_token_round_trips():
    payload = decode_token(create_access_token(subject=SUBJECT))
    assert payload["sub"] == SUBJECT
    assert payload["type"] == ACCESS_TOKEN_TYPE


def test_refresh_token_rejected_as_access_token():
    """Type confusion: a 7-day credential must not open a protected route."""
    with pytest.raises(HTTPException) as exc:
        decode_token(create_refresh_token(subject=SUBJECT))
    assert exc.value.status_code == 401
    assert exc.value.detail == "Invalid token type."


def test_access_token_rejected_as_refresh_token():
    with pytest.raises(HTTPException):
        decode_token(create_access_token(subject=SUBJECT), REFRESH_TOKEN_TYPE)


def test_unsigned_token_rejected():
    """`alg: none` is why the accepted list is hardcoded, not read from config."""
    forged = jwt.encode(
        {"sub": SUBJECT, "type": ACCESS_TOKEN_TYPE, "exp": 9999999999, "iat": 0},
        key="",
        algorithm="none",
    )
    with pytest.raises(HTTPException):
        decode_token(forged)


def test_token_without_expiry_rejected():
    """PyJWT validates `exp` only when present — without REQUIRED_CLAIMS a token
    minted with no expiry would be valid forever."""
    no_exp = jwt.encode(
        {"sub": SUBJECT, "type": ACCESS_TOKEN_TYPE, "iat": 0},
        settings.SECRET_KEY,
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        decode_token(no_exp)


def test_expired_token_rejected():
    expired = create_access_token(subject=SUBJECT, expires_delta=timedelta(seconds=-1))
    with pytest.raises(HTTPException):
        decode_token(expired)


def test_token_signed_with_another_key_rejected():
    other = jwt.encode(
        {
            "sub": SUBJECT,
            "type": ACCESS_TOKEN_TYPE,
            "exp": datetime.now(UTC) + timedelta(minutes=5),
            "iat": datetime.now(UTC),
        },
        "a-different-secret-entirely-but-long-enough-for-hs256",
        algorithm="HS256",
    )
    with pytest.raises(HTTPException):
        decode_token(other)


def test_accepted_algorithms_exclude_none():
    assert "none" not in ACCEPTED_ALGORITHMS
