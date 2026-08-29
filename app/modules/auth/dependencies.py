# app/modules/auth/dependencies.py
from app.config import settings
from app.core.exceptions import ForbiddenException
from app.modules.auth.constants import REGISTRATION_DISABLED_MSG


async def registration_enabled() -> None:
    """Close /register when signups are turned off via REGISTRATION_ENABLED.

    A route dependency rather than middleware: this is auth-module policy, not
    transport. /register stays public either way, so with signups off it answers
    403 (not 401) and login is unaffected — existing accounts keep working.
    """
    if not settings.REGISTRATION_ENABLED:
        raise ForbiddenException(REGISTRATION_DISABLED_MSG)
