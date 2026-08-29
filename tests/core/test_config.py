"""Settings validation. These are security controls, not preferences."""

import pytest
from pydantic import ValidationError

from app.config import PLACEHOLDER_SECRET_KEY, Settings

_BASE = {"DATABASE_URL": "sqlite+aiosqlite:///:memory:", "_env_file": None}


def test_placeholder_secret_key_rejected_in_production():
    with pytest.raises(ValidationError, match="placeholder"):
        Settings(APP_ENV="production", SECRET_KEY=PLACEHOLDER_SECRET_KEY, **_BASE)


def test_short_secret_key_rejected_in_production():
    with pytest.raises(ValidationError, match="at least 32 characters"):
        Settings(APP_ENV="production", SECRET_KEY="too-short", **_BASE)


def test_placeholder_secret_key_allowed_in_development():
    """Dev must stay frictionless — the gate is for everything else."""
    settings = Settings(APP_ENV="local", SECRET_KEY=PLACEHOLDER_SECRET_KEY, **_BASE)
    assert settings.is_dev is True


def test_wildcard_cors_origin_rejected():
    """ "*" with credentials lets any site make authenticated calls."""
    with pytest.raises(ValidationError, match=r"cannot contain"):
        Settings(SECRET_KEY="x" * 32, CORS_ORIGINS=["*"], **_BASE)


def test_unknown_environment_rejected():
    """APP_ENV gates HSTS, docs and error verbosity — a typo must not pass."""
    with pytest.raises(ValidationError):
        Settings(APP_ENV="prod", SECRET_KEY="x" * 32, **_BASE)


def test_testserver_host_added_only_for_test_envs():
    test_settings = Settings(APP_ENV="test", SECRET_KEY="x" * 32, **_BASE)
    prod_settings = Settings(APP_ENV="production", SECRET_KEY="x" * 32, **_BASE)
    assert "testserver" in test_settings.ALLOWED_HOSTS
    assert "testserver" not in prod_settings.ALLOWED_HOSTS
