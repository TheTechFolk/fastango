# app/core/constants.py
"""
Fastango — Global constants.

The fallback tier. Every module keeps its own specific wording in
app/modules/<name>/constants.py; these fill in when nothing more specific
applies, so no message string is written twice.
"""

from enum import Enum

# ── Generic Outcomes ──────────────────────────────────────────────────────────
SUCCESS_MSG = "Request processed successfully."
ERROR_MSG = "Internal server error. Please try again later."

# ── Exception Defaults ────────────────────────────────────────────────────────
# Each AppException subclass carries one of these as its class-level default.
VALIDATION_ERROR_MSG = "Invalid request data. Please check your input and try again."
UNAUTHORIZED_MSG = "Authentication credentials were not provided or are invalid."
FORBIDDEN_MSG = "You do not have permission to perform this action."
NOT_FOUND_MSG = "Resource not found."
ALREADY_EXISTS_MSG = "Resource already exists."
RATE_LIMITED_MSG = "Too many requests. Please slow down and try again shortly."
SERVICE_UNAVAILABLE_MSG = "Service temporarily unavailable. Please try again shortly."

# ── JWT ───────────────────────────────────────────────────────────────────────
# The `type` claim. Both sides need it: auth/utils.py stamps it when signing,
# core/security.py asserts it when decoding — and core must not import a module.
ACCESS_TOKEN_TYPE = "access"
REFRESH_TOKEN_TYPE = "refresh"


class RoleType(str, Enum):
    """Account roles.

    Lives in core, not in a module, for the same reason the token-type claims
    do: core/security.py reads the role off every request, and core importing
    from app.modules would invert the dependency the module registry rests on —
    delete the auth module and the whole app would stop booting.

    The role is signed into the JWT, so a demotion takes effect no sooner than
    the token expires. Fine for coarse gating, not for revocation.
    """

    USER = "USER"
    ADMIN = "ADMIN"
