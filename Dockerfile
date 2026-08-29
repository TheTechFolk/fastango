# syntax=docker/dockerfile:1

# ── Builder ───────────────────────────────────────────────────────────────────
# Dependencies are resolved and installed here so the toolchain never reaches
# the runtime image. --no-dev keeps pytest, ruff and pre-commit out of
# production; they ship by accident whenever dev tools sit in the runtime
# dependency list.
FROM python:3.12-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

COPY --from=ghcr.io/astral-sh/uv:0.11 /uv /usr/local/bin/uv

WORKDIR /app

# Lockfile first, source second: dependencies re-resolve only when they change.
COPY pyproject.toml uv.lock ./
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --no-install-project


# ── Runtime ───────────────────────────────────────────────────────────────────
FROM python:3.12-slim AS runtime

# PYTHONUNBUFFERED so container logs are not withheld inside a buffer;
# PYTHONDONTWRITEBYTECODE so no .pyc files are written into the layer.
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PATH="/app/.venv/bin:$PATH"

# Non-root. An arbitrary-write bug in the app should not be an arbitrary-write
# bug as uid 0.
RUN groupadd --system --gid 1001 app \
    && useradd --system --uid 1001 --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --chown=app:app alembic.ini ./
COPY --chown=app:app alembic ./alembic
COPY --chown=app:app app ./app

USER app

EXPOSE 8000

# /health is liveness only — it deliberately touches nothing, so a database
# outage drains rather than kills. /health/ready is the one to route on.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2).status == 200 else 1)"

# --proxy-headers is what makes the rate-limiter key and the audit log record
# the real client rather than the ingress. Without it every caller shares one
# rate-limit bucket.
CMD ["uvicorn", "app.main:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--proxy-headers", \
     "--forwarded-allow-ips", "*"]
