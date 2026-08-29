"""Auth services called directly, without an HTTP request in flight.

This is what `request_session` exists for — the fixture that pays for the
service-locator trade in app/database.py.
"""

import uuid

import pytest

from app.core.exceptions import UnauthorizedException, ValidationException
from app.modules.auth.repositories import AuthRepository
from app.modules.auth.schemas import LoginSchema, RegisterSchema
from app.modules.auth.services import AccountService, AuthService
from app.modules.auth.utils import dummy_hash, hash_password, verify_password

CREDENTIALS = {"email": "svc@example.com", "password": "SuperSecretPassword123"}


@pytest.mark.asyncio
async def test_register_then_login(request_session):
    data, message = await AuthService(RegisterSchema(**CREDENTIALS)).register()
    assert data["access_token"]
    assert message == "Account created successfully."

    data, message = await AuthService(LoginSchema(**CREDENTIALS)).login()
    assert data["access_token"]
    assert message == "Login successful."


@pytest.mark.asyncio
async def test_duplicate_email_raises_validation_not_conflict(request_session):
    await AuthService(RegisterSchema(**CREDENTIALS)).register()
    with pytest.raises(ValidationException):
        await AuthService(RegisterSchema(**CREDENTIALS)).register()


@pytest.mark.asyncio
async def test_login_unknown_email_raises_unauthorized(request_session):
    with pytest.raises(UnauthorizedException):
        await AuthService(LoginSchema(**CREDENTIALS)).login()


@pytest.mark.asyncio
async def test_deactivated_account_cannot_log_in(request_session):
    await AuthService(RegisterSchema(**CREDENTIALS)).register()

    # The read above autobegins a transaction, so commit into that one rather
    # than opening a nested `begin()` — the same lifecycle the HTTP fixtures
    # reproduce in _override_get_db.
    record = await AuthRepository.get_by_email(request_session, "svc@example.com")
    record.is_active = False
    await request_session.commit()

    with pytest.raises(UnauthorizedException):
        await AuthService(LoginSchema(**CREDENTIALS)).login()


@pytest.mark.asyncio
async def test_me_raises_for_an_unknown_code(request_session):
    with pytest.raises(UnauthorizedException):
        await AccountService(uuid.uuid4()).me()


def test_password_hashing_round_trips():
    hashed = hash_password("correct horse battery staple")
    assert verify_password("correct horse battery staple", hashed) is True
    assert verify_password("wrong", hashed) is False


def test_verify_password_returns_false_on_a_malformed_hash():
    """A corrupt stored hash is a failed login, never a 500."""
    assert verify_password("anything", "not-a-bcrypt-hash") is False


def test_dummy_hash_is_a_real_hash_nothing_matches():
    value = dummy_hash()
    assert value.startswith("$2")
    assert verify_password("", value) is False
    # Cached, so the ~300ms cost is paid once and not at import.
    assert dummy_hash() is value
