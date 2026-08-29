# app/core/rate_limit.py
"""
Per-IP rate limiter built on slowapi. Mitigates credential stuffing on
/auth/login and mass-account creation on /auth/register.

Two things here are load-bearing and are wrong by default:

- The key. `get_remote_address` reads request.client.host, which behind any
  ingress is the proxy for every caller. That collapses the entire internet
  into one counter, turning a 5/minute login limit into a DoS on your own
  login endpoint rather than a limit on an attacker.
- The storage. In-memory means per-worker, so `--workers 4` quietly multiplies
  every limit by four.
"""

import logging

from limits.errors import ConfigurationError
from slowapi import Limiter
from starlette.requests import Request

from app.config import settings
from app.core.context import client_ip

logger = logging.getLogger("fastango")


def rate_limit_key(request: Request) -> str:
    """The caller's address, honouring the proxy chain."""
    return client_ip(request)


def _build_limiter() -> Limiter:
    """Redis-backed where possible, in-memory where not — and say which.

    A misconfigured Redis must not stop the app booting, but the fallback is a
    materially weaker limit, so it is logged at WARNING rather than absorbed.
    """
    uri = settings.REDIS_URL or None
    if uri:
        try:
            return Limiter(
                key_func=rate_limit_key,
                enabled=settings.RATE_LIMIT_ENABLED,
                storage_uri=uri,
            )
        except (ConfigurationError, ImportError):
            logger.warning(
                "REDIS_URL is set but the redis backend is unavailable — rate limits "
                "fall back to in-memory storage and are per-worker."
            )
    return Limiter(key_func=rate_limit_key, enabled=settings.RATE_LIMIT_ENABLED)


limiter = _build_limiter()
