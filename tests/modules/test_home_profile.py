import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession


@pytest.mark.asyncio
async def test_get_home_success(client: AsyncClient):
    """Verify home dashboard endpoint returns successfully."""
    # In APP_ENV=test, get_current_user_code returns a mock UUID when no
    # Authorization header is sent.
    response = await client.get("/api/v1/home")
    assert response.status_code == 200

    resp_json = response.json()
    assert resp_json["error"] is False
    assert resp_json["message"] == "Home screen data retrieved successfully."
    assert resp_json["data"]["welcome_message"] == "Welcome to the Fastango platform!"
    assert resp_json["data"]["user_code"] == "3fa85f64-5717-4562-b3fc-2c963f66afa6"


@pytest.mark.asyncio
async def test_get_profile_not_found(client: AsyncClient):
    """Verify profile endpoint returns 404 if the user doesn't exist in db."""
    response = await client.get("/api/v1/profile")
    assert response.status_code == 404
    assert response.json()["detail"] == "Profile not found."


@pytest.mark.asyncio
async def test_get_profile_success(client: AsyncClient, db_session: AsyncSession):
    """Verify profile endpoint returns successfully when user exists in DB."""
    register_payload = {
        "email": "profileuser@fastango.com",
        "password": "SecretPassword123",
    }
    reg_resp = await client.post("/api/v1/auth/register", json=register_payload)
    assert reg_resp.status_code == 201

    token = reg_resp.json()["data"]["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    response = await client.get("/api/v1/profile", headers=headers)
    assert response.status_code == 200

    resp_json = response.json()
    assert resp_json["error"] is False
    assert resp_json["message"] == "Profile details retrieved successfully."
    assert resp_json["data"]["email"] == "profileuser@fastango.com"
    # Public registration must never grant superuser, even though the schema
    # used to accept the field. This locks in the regression.
    assert resp_json["data"]["is_superuser"] is False
    assert resp_json["data"]["is_active"] is True
