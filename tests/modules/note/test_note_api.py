"""Notes over HTTP: the reference CRUD module, through the full stack."""

import uuid

import pytest_asyncio

from app.core.registry import PRIVATE_ROOT, PUBLIC_ROOT

NOTES = f"{PRIVATE_ROOT}/notes"
REGISTER = f"{PUBLIC_ROOT}/auth/register"


async def _register(anon_client, email: str) -> dict[str, str]:
    """A real account's auth header. Notes carry a foreign key to their owner,
    so the unregistered identity behind the `client` fixture cannot own one."""
    resp = await anon_client.post(
        REGISTER, json={"email": email, "password": "SuperSecretPassword123"}
    )
    return {"Authorization": f"Bearer {resp.json()['data']['access_token']}"}


@pytest_asyncio.fixture
async def alice(anon_client) -> dict[str, str]:
    return await _register(anon_client, "alice@example.com")


@pytest_asyncio.fixture
async def bob(anon_client) -> dict[str, str]:
    return await _register(anon_client, "bob@example.com")


async def _create(anon_client, headers, title="Groceries", body="milk") -> dict:
    resp = await anon_client.post(NOTES, json={"title": title, "body": body}, headers=headers)
    assert resp.status_code == 201
    return resp.json()["data"]


async def test_create_then_get(anon_client, alice):
    note = await _create(anon_client, alice)
    assert note["title"] == "Groceries"
    assert note["body"] == "milk"
    assert "id" not in note and "owner_code" not in note

    resp = await anon_client.get(f"{NOTES}/{note['code']}", headers=alice)
    assert resp.status_code == 200
    assert resp.json()["data"] == note


async def test_create_ignores_a_client_supplied_owner(anon_client, alice, bob):
    """The owner is the token's subject. A body field must not override it."""
    resp = await anon_client.post(
        NOTES, json={"title": "Mine", "owner_code": str(uuid.uuid4())}, headers=alice
    )
    assert resp.status_code == 201
    listed = await anon_client.get(NOTES, headers=alice)
    assert listed.json()["data"]["total"] == 1


async def test_list_is_paginated_and_newest_first(anon_client, alice):
    for n in range(3):
        await _create(anon_client, alice, title=f"note {n}")

    first = (await anon_client.get(NOTES, params={"limit": 2}, headers=alice)).json()["data"]
    assert [n["title"] for n in first["items"]] == ["note 2", "note 1"]
    assert (first["limit"], first["offset"], first["total"]) == (2, 0, 3)

    rest = await anon_client.get(NOTES, params={"limit": 2, "offset": 2}, headers=alice)
    assert [n["title"] for n in rest.json()["data"]["items"]] == ["note 0"]


async def test_list_limit_is_bounded(anon_client, alice):
    resp = await anon_client.get(NOTES, params={"limit": 100_000}, headers=alice)
    assert resp.status_code == 422
    assert set(resp.json()["data"]) == {"limit"}


async def test_patch_changes_only_the_fields_sent(anon_client, alice):
    note = await _create(anon_client, alice)
    resp = await anon_client.patch(
        f"{NOTES}/{note['code']}", json={"title": "Shopping"}, headers=alice
    )
    assert resp.status_code == 200
    assert resp.json()["data"]["title"] == "Shopping"
    assert resp.json()["data"]["body"] == "milk"


async def test_delete_then_gone(anon_client, alice):
    note = await _create(anon_client, alice)
    url = f"{NOTES}/{note['code']}"

    assert (await anon_client.delete(url, headers=alice)).status_code == 200
    assert (await anon_client.get(url, headers=alice)).status_code == 404
    assert (await anon_client.delete(url, headers=alice)).status_code == 404


async def test_another_users_note_is_invisible(anon_client, alice, bob):
    """404 for every verb, not 403 — a 403 would confirm the note exists."""
    url = f"{NOTES}/{(await _create(anon_client, alice))['code']}"

    assert (await anon_client.get(url, headers=bob)).status_code == 404
    assert (await anon_client.patch(url, json={"title": "x"}, headers=bob)).status_code == 404
    assert (await anon_client.delete(url, headers=bob)).status_code == 404
    assert (await anon_client.get(NOTES, headers=bob)).json()["data"]["total"] == 0
    # And Alice's note survived all of it, unchanged.
    assert (await anon_client.get(url, headers=alice)).json()["data"]["title"] == "Groceries"


async def test_empty_title_rejected(anon_client, alice):
    resp = await anon_client.post(NOTES, json={"title": ""}, headers=alice)
    assert resp.status_code == 422
    assert set(resp.json()["data"]) == {"title"}


async def test_anonymous_is_401(anon_client):
    assert (await anon_client.get(NOTES)).status_code == 401
    assert (await anon_client.post(NOTES, json={"title": "x"})).status_code == 401
