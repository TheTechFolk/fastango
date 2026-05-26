# app/core/rate_limit.py
"""
Per-IP rate limiter built on slowapi. Mitigates credential stuffing on
/auth/login and mass-account creation on /auth/register.

Note: the default in-memory backend is per-worker, so multi-worker deployments
should configure a Redis backend via slowapi's storage_uri parameter.
"""

from slowapi import Limiter
from slowapi.util import get_remote_address

from app.config import settings

limiter = Limiter(
    key_func=get_remote_address,
    enabled=settings.RATE_LIMIT_ENABLED,
)
