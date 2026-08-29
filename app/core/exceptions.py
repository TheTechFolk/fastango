# app/core/exceptions.py
"""
Fastango — Application Exceptions

Each exception carries both its HTTP status and its default message, so no call
site ever writes a status code. `app/exceptions.py` registers a single handler
for the whole family and reads both off the instance — adding a new type never
requires touching a handler.

    raise NotFoundException()                      -> 404, "Resource not found."
    raise UnauthorizedException("Bad password.")   -> 401, "Bad password."
"""

from app.core.constants import (
    ALREADY_EXISTS_MSG,
    ERROR_MSG,
    FORBIDDEN_MSG,
    NOT_FOUND_MSG,
    UNAUTHORIZED_MSG,
    VALIDATION_ERROR_MSG,
)


class AppException(Exception):
    """Base class for all custom Fastango application exceptions."""

    status_code: int = 500
    message: str = ERROR_MSG

    def __init__(self, message: str | None = None):
        # Caller's message wins; the class default fills in.
        self.message = message or self.message
        super().__init__(self.message)


class ValidationException(AppException):
    """Business-rule validation failed inside a service."""

    status_code = 400
    message = VALIDATION_ERROR_MSG


class UnauthorizedException(AppException):
    """The request is unauthenticated, or its credentials are wrong."""

    status_code = 401
    message = UNAUTHORIZED_MSG


class ForbiddenException(AppException):
    """The caller is authenticated but lacks permission."""

    status_code = 403
    message = FORBIDDEN_MSG


class NotFoundException(AppException):
    """A requested resource does not exist."""

    status_code = 404
    message = NOT_FOUND_MSG


class AlreadyExistsException(AppException):
    """A resource being created already exists.

    Do NOT use this for account registration: a 409 confirms the email is
    taken, which is exactly what the generic registration message exists to
    hide. Use ValidationException there so the status keeps the same secret
    the wording does.
    """

    status_code = 409
    message = ALREADY_EXISTS_MSG
