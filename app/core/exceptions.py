# app/core/exceptions.py
from fastapi import HTTPException, status


class FastangoException(Exception):
    """Base class for all custom Fastango application exceptions."""

    def __init__(self, message: str = "An unexpected error occurred."):
        self.message = message
        super().__init__(self.message)


class NotFoundException(FastangoException):
    """Raised when a requested resource is not found."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} not found.")


class AlreadyExistsException(FastangoException):
    """Raised when attempting to create a resource that already exists."""

    def __init__(self, resource: str = "Resource"):
        super().__init__(f"{resource} already exists.")


class UnauthorizedException(FastangoException):
    """Raised when an unauthenticated request is made to a protected route."""

    def __init__(self, message: str = "Authentication credentials were not provided."):
        super().__init__(message)


class ForbiddenException(FastangoException):
    """Raised when an authenticated user lacks permission for an action."""

    def __init__(self, message: str = "You do not have permission to perform this action."):
        super().__init__(message)


class ValidationException(FastangoException):
    """Raised when business-rule validation fails inside a service layer."""

    def __init__(self, message: str = "Validation failed."):
        super().__init__(message)


class ServiceException(FastangoException):
    """Generic service-layer exception for unexpected business logic failures."""

    def __init__(self, message: str = "A service error occurred."):
        super().__init__(message)


# ── HTTP Exception shortcuts ─────────────────────────────────────────────────

def http_404(detail: str = "Not found") -> HTTPException:
    return HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=detail)


def http_400(detail: str = "Bad request") -> HTTPException:
    return HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=detail)


def http_401(detail: str = "Unauthorized") -> HTTPException:
    return HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=detail)


def http_403(detail: str = "Forbidden") -> HTTPException:
    return HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=detail)


def http_409(detail: str = "Conflict") -> HTTPException:
    return HTTPException(status_code=status.HTTP_409_CONFLICT, detail=detail)
