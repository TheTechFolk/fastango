"""The public/private boundary, security headers, and request correlation.

These are the tests that prove the routing convention is a security control and
not just a naming scheme.
"""

import pytest

from app.core.context import REQUEST_ID_HEADER
from app.core.registry import PRIVATE_ROOT, PUBLIC_ROOT

PRIVATE_URL = f"{PRIVATE_ROOT}/auth/me"
PUBLIC_URL = f"{PUBLIC_ROOT}/auth/login"


@pytest.mark.asyncio
async def test_private_route_rejects_missing_token(anon_client):
    resp = await anon_client.get(PRIVATE_URL)
    assert resp.status_code == 401
    assert resp.headers["WWW-Authenticate"] == "Bearer"
    # The 401 keeps the envelope like every other status.
    assert resp.json()["error"] is True


@pytest.mark.asyncio
async def test_private_route_rejects_garbage_token(anon_client):
    resp = await anon_client.get(PRIVATE_URL, headers={"Authorization": "Bearer not-a-jwt"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_private_route_rejects_non_bearer_scheme(anon_client):
    resp = await anon_client.get(PRIVATE_URL, headers={"Authorization": "Basic abc123"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_public_route_needs_no_token(anon_client):
    """422 not 401: it got past auth and failed validation on an empty body."""
    resp = await anon_client.post(PUBLIC_URL, json={})
    assert resp.status_code == 422


@pytest.mark.asyncio
async def test_health_is_public_and_touches_nothing(anon_client):
    resp = await anon_client.get("/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_security_headers_present(anon_client):
    resp = await anon_client.get("/health")
    assert resp.headers["X-Content-Type-Options"] == "nosniff"
    assert resp.headers["X-Frame-Options"] == "DENY"
    assert resp.headers["Referrer-Policy"] == "no-referrer"
    assert resp.headers["Cross-Origin-Opener-Policy"] == "same-origin"
    assert "frame-ancestors 'none'" in resp.headers["Content-Security-Policy"]


@pytest.mark.asyncio
async def test_hsts_absent_in_dev(anon_client):
    """HSTS on a plain-http dev host would pin the browser to https for months."""
    resp = await anon_client.get("/health")
    assert "Strict-Transport-Security" not in resp.headers


@pytest.mark.asyncio
async def test_request_id_generated_and_returned(anon_client):
    resp = await anon_client.get("/health")
    assert resp.headers[REQUEST_ID_HEADER]


@pytest.mark.asyncio
async def test_upstream_request_id_propagated(anon_client):
    resp = await anon_client.get("/health", headers={REQUEST_ID_HEADER: "abc123"})
    assert resp.headers[REQUEST_ID_HEADER] == "abc123"


@pytest.mark.asyncio
async def test_malformed_upstream_request_id_replaced(anon_client):
    """It lands in logs — only accept something that looks like an id."""
    resp = await anon_client.get("/health", headers={REQUEST_ID_HEADER: "../../etc/passwd"})
    assert resp.headers[REQUEST_ID_HEADER] != "../../etc/passwd"


@pytest.mark.asyncio
async def test_unknown_route_is_401_to_anonymous_callers(anon_client):
    """Default-deny applies to paths that do not exist either, so an anonymous
    caller cannot map the route table by watching 404 vs 401."""
    resp = await anon_client.get("/no/such/path")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_unknown_route_uses_the_envelope(client):
    """An authenticated caller gets a real 404 — in the same envelope as
    everything else, not FastAPI's {"detail": ...}."""
    resp = await client.get("/no/such/path")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"] is True
    assert body["data"] is None
    assert "message" in body
