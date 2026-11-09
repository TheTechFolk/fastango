"""client_ip must not trust a client-supplied X-Forwarded-For."""

from starlette.requests import Request

from app.core.context import client_ip


def _request(headers: dict[str, str]) -> Request:
    return Request(
        {
            "type": "http",
            "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
            "client": ("203.0.113.7", 50000),
        }
    )


def test_spoofed_forwarded_for_is_ignored():
    """Rotating this header used to mint a fresh rate-limit bucket per request."""
    assert client_ip(_request({"X-Forwarded-For": "1.2.3.4"})) == "203.0.113.7"
    assert client_ip(_request({"X-Forwarded-For": "5.6.7.8, 9.9.9.9"})) == "203.0.113.7"
