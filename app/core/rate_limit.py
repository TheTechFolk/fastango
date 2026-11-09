# app/core/rate_limit.py
"""
Per-IP rate limiter built on slowapi. Mitigates credential stuffing on
/auth/login and mass-account creation on /auth/register.

Two things here are load-bearing and are wrong by default:

- The key. Behind an ingress the socket address is the proxy for everyone;
  uvicorn's --proxy-headers fixes that for trusted hops only (FORWARDED_ALLOW_IPS,
  see core/context.py). Trusting X-Forwarded-For directly lets a client
  rotate it for unlimited attempts.
- The storage. In-memory means per-worker, so `--workers 4` quietly multiplies
  every limit by four.
"""

import logging

from limits.errors import ConfigurationError
from slowapi import Limiter

from app.config import settings
from app.core.context import client_ip

logger = logging.getLogger("fastango")


def _build_limiter() -> Limiter:
    """Redis-backed where possible, in-memory where not — and say which.

    A misconfigured Redis must not stop the app booting, but the fallback is a
    materially weaker limit, so it is logged at WARNING rather than absorbed.
    """
    uri = settings.REDIS_URL or None
    if uri:
        try:
            return Limiter(
                key_func=client_ip,
                enabled=settings.RATE_LIMIT_ENABLED,
                storage_uri=uri,
            )
        except (ConfigurationError, ImportError):
            logger.warning(
                "REDIS_URL is set but the redis backend is unavailable — rate limits "
                "fall back to in-memory storage and are per-worker."
            )
    return Limiter(key_func=client_ip, enabled=settings.RATE_LIMIT_ENABLED)


limiter = _build_limiter()
