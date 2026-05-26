import pytest
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.modules.auth.models import AdminAuth


@pytest.mark.asyncio
async def test_admin_registration_success(client: AsyncClient, db_session: AsyncSession):
    """Verify that a new admin can be registered successfully."""
    payload = {
        "email": "newadmin@fastango.com",
        "password": "SuperSecretPassword123",
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    resp_json = response.json()
    assert resp_json["error"] is False
    assert resp_json["message"] == "Admin account created successfully."
    assert "access_token" in resp_json["data"]
    assert "refresh_token" in resp_json["data"]
    assert resp_json["data"]["token_type"] == "bearer"

    # Verify admin was saved in database with is_superuser forced to False —
    # regardless of any user input. Public registration may not elevate.
    result = await db_session.execute(
        select(AdminAuth).where(AdminAuth.email == "newadmin@fastango.com")
    )
    admin = result.scalars().first()
    assert admin is not None
    assert admin.is_superuser is False


@pytest.mark.asyncio
async def test_admin_registration_ignores_is_superuser_field(
    client: AsyncClient, db_session: AsyncSession
):
    """
    Privilege-escalation regression: even if a client sends is_superuser=true,
    the server must ignore it and create a non-privileged account.
    """
    payload = {
        "email": "attacker@fastango.com",
        "password": "SuperSecretPassword123",
        "is_superuser": True,  # MUST be ignored by the server.
    }

    response = await client.post("/api/v1/auth/register", json=payload)
    assert response.status_code == 201

    result = await db_session.execute(
        select(AdminAuth).where(AdminAuth.email == "attacker@fastango.com")
    )
    admin = result.scalars().first()
    assert admin is not None
    assert admin.is_superuser is False, (
        "SECURITY: registration must never honor a client-supplied is_superuser"
    )


@pytest.mark.asyncio
async def test_admin_registration_duplicate_email(client: AsyncClient, db_session: AsyncSession):
    """Verify duplicate registration returns 400 with a generic, non-enumerating message."""
    payload = {
        "email": "duplicate@fastango.com",
        "password": "SuperSecretPassword123"
    }

    resp1 = await client.post("/api/v1/auth/register", json=payload)
    assert resp1.status_code == 201

    resp2 = await client.post("/api/v1/auth/register", json=payload)
    assert resp2.status_code == 400
    # Generic message — must not confirm "this email is already registered".
    assert resp2.json()["detail"] == "Unable to register with the provided credentials."


@pytest.mark.asyncio
async def test_admin_login_success(client: AsyncClient, db_session: AsyncSession):
    """Verify that an existing admin can login successfully with correct credentials."""
    register_payload = {
        "email": "loginadmin@fastango.com",
        "password": "SecretPassword123",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201

    login_payload = {
        "email": "loginadmin@fastango.com",
        "password": "SecretPassword123"
    }
    login_resp = await client.post("/api/v1/auth/login", json=login_payload)
    assert login_resp.status_code == 200

    resp_json = login_resp.json()
    assert resp_json["error"] is False
    assert resp_json["message"] == "Admin login successful."
    assert "access_token" in resp_json["data"]
    assert "refresh_token" in resp_json["data"]


@pytest.mark.asyncio
async def test_admin_login_invalid_credentials(client: AsyncClient):
    """Verify login fails with a 401 when using wrong email or password."""
    payload = {
        "email": "nonexistent@fastango.com",
        "password": "WrongPassword123"
    }
    response = await client.post("/api/v1/auth/login", json=payload)
    assert response.status_code == 401
    assert response.json()["detail"] == "Invalid email or password."


@pytest.mark.asyncio
async def test_refresh_token_rejected_as_access_token(client: AsyncClient):
    """
    JWT type-confusion regression: a refresh token must NOT be accepted in
    the Authorization header of a protected endpoint.
    """
    register_payload = {
        "email": "tokenuser@fastango.com",
        "password": "SuperSecretPassword123",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201
    refresh_token = reg_resp.json()["data"]["refresh_token"]

    headers = {"Authorization": f"Bearer {refresh_token}"}
    resp = await client.get("/api/v1/profile", headers=headers)
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid token type."
