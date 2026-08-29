# app/config.py
from functools import lru_cache
from pathlib import Path
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Environment names, in one place. Several files used to keep their own tuple
# and they drift apart — the auth path treating "local" as production while the
# error path treats it as dev is how a bypass ships.
Environment = Literal["local", "test", "testing", "staging", "production"]
DEV_ENVS: tuple[Environment, ...] = ("local", "test", "testing")
TEST_ENVS: tuple[Environment, ...] = ("test", "testing")

# Anchored to the package, not the process. A relative env_file resolves against
# the working directory, so running uvicorn from anywhere but the repo root
# silently skips the file and fails on the required keys instead.
_ENV_FILE = Path(__file__).resolve().parent.parent / "local.env"

# The value shipped in local.env.example. It is a working HS256 key, so nothing
# stops it reaching production except the check below.
PLACEHOLDER_SECRET_KEY = "super-secret-dev-key-change-in-production-to-long-random-string"
MIN_SECRET_KEY_LENGTH = 32


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=_ENV_FILE,
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "Fastango"
    # A Literal, not a str: this one value gates HSTS, whether exception detail
    # reaches the client, and whether /docs is published. A typo would
    # otherwise change branch silently.
    APP_ENV: Environment = "local"
    APP_DEBUG: bool = False
    APP_VERSION: str = "1.0.0"
    # No default — Pydantic raises ValidationError at startup if unset. A
    # forgotten SECRET_KEY in production must fail fast, never silently use a
    # known string.
    SECRET_KEY: str
    # Allowed Host header values. Conservative dev default; in production this
    # MUST be tightened to your real hostnames. "testserver" is httpx's host and
    # is added for test environments only, below.
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1"]

    # ── Modules ───────────────────────────────────────────────────────────
    # Which modules under app/modules/ get their routers mounted.
    # ENABLED_MODULES empty  → mount every discovered module (default).
    # ENABLED_MODULES set    → mount only the listed modules.
    # DISABLED_MODULES       → never mount these, even if listed as enabled.
    # Disabled modules keep their models imported so Alembic migrations stay
    # complete (disabled ≠ uninstalled, same as Django).
    ENABLED_MODULES: list[str] = []
    DISABLED_MODULES: list[str] = []

    # ── Database ──────────────────────────────────────────────────────────
    # No default — fail fast if missing. local.env provides it for development.
    DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20
    # Recycle before a proxy or NAT idle-timeout can close a pooled connection
    # underneath us; pre-ping alone turns that into a retry on every checkout.
    DB_POOL_RECYCLE_SECONDS: int = 1800

    # ── Authentication ────────────────────────────────────────────────────
    # Close self-service signup without a code change. Read per request, so
    # flipping it takes effect on the next call. Login is unaffected — existing
    # accounts keep working when registration is off.
    REGISTRATION_ENABLED: bool = True
    # The bcrypt cost factor. Explicit because the library default drifts
    # between releases, and a silently-changing security parameter is not one.
    BCRYPT_ROUNDS: int = 12

    # ── JWT Authentication ─────────────────────────────────────────────────
    # Signing algorithm only. The *accepted* algorithms on decode are a
    # hardcoded constant in core/security.py — taking that list from config is
    # how "alg: none" gets accepted.
    JWT_ALGORITHM: Literal["HS256", "HS384", "HS512"] = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"

    # ── Redis ─────────────────────────────────────────────────────────────
    # Backs the rate limiter. Empty falls back to in-memory storage, which is
    # per-worker — fine for one process, wrong for any real deployment.
    REDIS_URL: str = ""

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]

    # ── Validation ────────────────────────────────────────────────────────
    @field_validator("CORS_ORIGINS")
    @classmethod
    def _reject_wildcard_origin(cls, value: list[str]) -> list[str]:
        """ "*" plus credentials means any site can make authenticated calls.

        Starlette echoes the request Origin when allow_origins is "*" and
        allow_credentials is on, and this app sets credentials on. Reject the
        combination here rather than discovering it from a browser.
        """
        if "*" in value:
            raise ValueError(
                "CORS_ORIGINS cannot contain '*' — credentials are enabled, so "
                "list the exact origins instead."
            )
        return value

    @model_validator(mode="after")
    def _validate_secret_key(self) -> "Settings":
        """Reject a weak or placeholder SECRET_KEY outside development.

        HS256 with a low-entropy key is brute-forceable offline from a single
        captured token, so this is the difference between "signed" and "signed
        by anyone who read the example file".
        """
        if self.APP_ENV in DEV_ENVS:
            return self
        if self.SECRET_KEY == PLACEHOLDER_SECRET_KEY:
            raise ValueError(
                "SECRET_KEY is still the placeholder from local.env.example. "
                "Generate one with `openssl rand -hex 32`."
            )
        if len(self.SECRET_KEY) < MIN_SECRET_KEY_LENGTH:
            raise ValueError(
                f"SECRET_KEY must be at least {MIN_SECRET_KEY_LENGTH} characters "
                f"outside development (got {len(self.SECRET_KEY)})."
            )
        return self

    @model_validator(mode="after")
    def _allow_test_host(self) -> "Settings":
        """httpx's ASGI transport sends `Host: testserver`.

        Added for test environments only. It used to sit in the production
        default, where TrustedHostMiddleware would accept it from anyone.
        """
        if self.APP_ENV in TEST_ENVS and "testserver" not in self.ALLOWED_HOSTS:
            self.ALLOWED_HOSTS = [*self.ALLOWED_HOSTS, "testserver"]
        return self

    # ── Derived ───────────────────────────────────────────────────────────
    @property
    def is_dev(self) -> bool:
        """Dev environments get exception detail in responses, docs, and no HSTS."""
        return self.APP_ENV in DEV_ENVS


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()


settings: Settings = get_settings()
