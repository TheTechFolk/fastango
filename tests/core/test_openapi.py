"""The OpenAPI schema must describe the errors the app really returns."""

from app.core.registry import PRIVATE_ROOT, PUBLIC_ROOT
from app.main import app

ERROR_REF = {"$ref": "#/components/schemas/ErrorResponse"}


def _error_schema(path: str, method: str, status: int) -> dict:
    operation = app.openapi()["paths"][path][method]
    return operation["responses"][str(status)]["content"]["application/json"]["schema"]


def test_validation_errors_are_documented_in_the_envelope():
    """FastAPI's default {"detail": [...]} shape is never emitted, so it must
    not be what a generated client is told to expect."""
    assert "HTTPValidationError" not in app.openapi()["components"]["schemas"]
    assert _error_schema(f"{PUBLIC_ROOT}/auth/login", "post", 422) == ERROR_REF


def test_private_routes_document_401():
    assert _error_schema(f"{PRIVATE_ROOT}/notes", "get", 401) == ERROR_REF


def test_routes_document_their_own_errors():
    assert _error_schema(f"{PRIVATE_ROOT}/notes/{{code}}", "get", 404) == ERROR_REF
    assert _error_schema(f"{PUBLIC_ROOT}/auth/login", "post", 429) == ERROR_REF
