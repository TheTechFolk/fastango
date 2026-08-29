"""Auth over HTTP: the full middleware and handler stack."""

import pytest
from sqlalchemy import select

from app.core.constants import RoleType
from app.core.registry import PRIVATE_ROOT, PUBLIC_ROOT
from app.modules.auth.models import Auth

REGISTER = f"{PUBLIC_ROOT}/auth/register"
LOGIN = f"{PUBLIC_ROOT}/auth/login"
REFRESH = f"{PUBLIC_ROOT}/auth/refresh"
ME = f"{PRIVATE_ROOT}/auth/me"

CREDENTIALS = {"email": "user@example.com", "password": "SuperSecretPassword123"}


@pytest.mark.asyncio
async def test_register_returns_a_token_pair(anon_client, db_session):
    resp = await anon_client.post(REGISTER, json=CREDENTIALS)
    assert resp.status_code == 201

    body = resp.json()
    assert body["error"] is False
    assert body["data"]["token_type"] == "bearer"
    assert body["data"]["access_token"] and body["data"]["refresh_token"]

    record = (
        (await db_session.execute(select(Auth).where(Auth.email == "user@example.com")))
        .scalars()
        .first()
    )
    assert record is not None
    assert record.role == RoleType.USER.value


@pytest.mark.asyncio
async def test_register_ignores_a_client_supplied_role(anon_client, db_session):
    """Privilege-escalation regression: the body must never set the role."""
    resp = await anon_client.post(
        REGISTER, json={**CREDENTIALS, "role": "ADMIN", "is_superuser": True}
    )
    assert resp.status_code == 201

    record = (
        (await db_session.execute(select(Auth).where(Auth.email == "user@example.com")))
        .scalars()
        .first()
    )
    assert record.role == RoleType.USER.value, "registration must never honor a client role"


@pytest.mark.asyncio
async def test_register_normalizes_the_email(anon_client, db_session):
    """` Me@Example.com ` and `me@example.com` must be one account."""
    await anon_client.post(REGISTER, json={**CREDENTIALS, "email": "  User@Example.COM "})
    record = (
        (await db_session.execute(select(Auth).where(Auth.email == "user@example.com")))
        .scalars()
        .first()
    )
    assert record is not None


@pytest.mark.asyncio
async def test_duplicate_registration_does_not_confirm_the_email(anon_client):
    assert (await anon_client.post(REGISTER, json=CREDENTIALS)).status_code == 201
    second = await anon_client.post(REGISTER, json=CREDENTIALS)
    # 400, not 409: a conflict status confirms the address is taken, which is
    # exactly what the generic message exists to hide.
    assert second.status_code == 400
    assert second.json()["message"] == "Unable to register with the provided credentials."


@pytest.mark.asyncio
async def test_short_password_rejected(anon_client):
    resp = await anon_client.post(REGISTER, json={**CREDENTIALS, "password": "short"})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_login_succeeds_with_correct_credentials(anon_client):
    await anon_client.post(REGISTER, json=CREDENTIALS)
    resp = await anon_client.post(LOGIN, json=CREDENTIALS)
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_login_with_unknown_email_and_wrong_password_are_indistinguishable(anon_client):
    await anon_client.post(REGISTER, json=CREDENTIALS)

    unknown = await anon_client.post(
        LOGIN, json={"email": "nobody@example.com", "password": "whatever"}
    )
    wrong = await anon_client.post(LOGIN, json={**CREDENTIALS, "password": "WrongPassword123"})

    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json()["message"] == wrong.json()["message"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_me_returns_the_callers_account(anon_client):
    registered = await anon_client.post(REGISTER, json=CREDENTIALS)
    token = registered.json()["data"]["access_token"]

    resp = await anon_client.get(ME, headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    assert resp.json()["data"]["email"] == "user@example.com"
    assert resp.json()["data"]["role"] == RoleType.USER.value


@pytest.mark.asyncio
async def test_me_rejects_a_refresh_token(anon_client):
    """Type confusion, end to end through the middleware."""
    registered = await anon_client.post(REGISTER, json=CREDENTIALS)
    refresh_token = registered.json()["data"]["refresh_token"]

    resp = await anon_client.get(ME, headers={"Authorization": f"Bearer {refresh_token}"})
    assert resp.status_code == 401
    assert resp.json()["message"] == "Invalid token type."


@pytest.mark.asyncio
async def test_me_rejects_a_token_for_a_deleted_account(client):
    """The `client` fixture's identity was never registered — a valid token for
    an account that does not exist must not authenticate."""
    resp = await client.get(ME)
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_refresh_returns_a_new_pair(anon_client):
    registered = await anon_client.post(REGISTER, json=CREDENTIALS)
    refresh_token = registered.json()["data"]["refresh_token"]

    resp = await anon_client.post(REFRESH, json={"refresh_token": refresh_token})
    assert resp.status_code == 200
    assert resp.json()["data"]["access_token"]


@pytest.mark.asyncio
async def test_refresh_rejects_an_access_token(anon_client):
    registered = await anon_client.post(REGISTER, json=CREDENTIALS)
    access_token = registered.json()["data"]["access_token"]

    resp = await anon_client.post(REFRESH, json={"refresh_token": access_token})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_registration_can_be_closed(anon_client, monkeypatch):
    """403, not 401 — /register stays public, the policy just says no."""
    from app.config import settings

    monkeypatch.setattr(settings, "REGISTRATION_ENABLED", False)
    resp = await anon_client.post(REGISTER, json=CREDENTIALS)
    assert resp.status_code == 403
    # Login is unaffected by the switch.
    assert (await anon_client.post(LOGIN, json=CREDENTIALS)).status_code == 401
