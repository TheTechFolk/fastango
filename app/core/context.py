# app/core/context.py
"""
Fastango — Per-request context.

A 500 in the logs is unmatchable to a user's report without a correlation id:
the catch-all handler knows the method and path and nothing else. The id set
here travels into the audit line, the error log, and the X-Request-ID response
header, so those three can be joined after the fact.

`client_ip` lives here rather than in middleware.py because the rate limiter
needs it too, and importing middleware from rate_limit closes an import cycle.
"""

import uuid
from contextvars import ContextVar

from starlette.requests import Request

REQUEST_ID_HEADER = "X-Request-ID"

# Empty rather than unset: reading this off the request path must never raise,
# and code outside a request (a CLI, a test) should read "no request" cleanly.
request_id_ctx: ContextVar[str] = ContextVar("request_id", default="")


def new_request_id() -> str:
    """A fresh correlation id. Short — it is read off a log line by a human."""
    return uuid.uuid4().hex[:16]


def get_request_id() -> str:
    """The current request's id, or "-" outside a request."""
    return request_id_ctx.get() or "-"


def client_ip(request: Request) -> str:
    """The caller's address, honouring the proxy chain.

    Behind an ingress `request.client.host` is the proxy for every request, so
    the audit log records one address for the whole internet and the rate
    limiter buckets everyone into a single counter — turning a 5/minute login
    limit into a DoS on your own login endpoint. Uvicorn only rewrites
    request.client when started with --proxy-headers, so read the header here
    too and take the left-most entry, which is the original client.
    """
    forwarded = request.headers.get("x-forwarded-for", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"
