# app/config.py
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Centralized application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file="local.env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── Application ──────────────────────────────────────────────────────
    APP_NAME: str = "Fastango"
    APP_ENV: str = "local"
    APP_DEBUG: bool = False
    APP_VERSION: str = "1.0.0"
    # No default — Pydantic raises ValidationError at startup if unset.
    # This is intentional: a forgotten SECRET_KEY in production must fail fast,
    # never silently use a known string.
    SECRET_KEY: str
    # Allowed Host header values. Default is the conservative dev/test set; in
    # production this MUST be tightened to your actual hostnames via env var.
    ALLOWED_HOSTS: list[str] = ["localhost", "127.0.0.1", "testserver"]

    # ── Database ──────────────────────────────────────────────────────────
    # No default — fail fast if missing. local.env provides it for development.
    DATABASE_URL: str
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # ── JWT Authentication ─────────────────────────────────────────────────
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 7

    # ── Rate Limiting ─────────────────────────────────────────────────────
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_LOGIN: str = "5/minute"
    RATE_LIMIT_REGISTER: str = "3/minute"

    # ── Redis ─────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"

    # ── AWS S3 Storage ────────────────────────────────────────────────────
    AWS_ACCESS_KEY_ID: str = ""
    AWS_SECRET_ACCESS_KEY: str = ""
    AWS_S3_BUCKET_NAME: str = "fastango-media"
    AWS_S3_REGION: str = "us-east-1"

    # ── CORS ──────────────────────────────────────────────────────────────
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://localhost:8000"]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return a cached singleton of Settings."""
    return Settings()


settings: Settings = get_settings()
