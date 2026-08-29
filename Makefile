# Fastango — the manage.py replacement.
# Recipes use the `target: ; command` form so nothing breaks on tabs vs spaces.

.PHONY: help setup dev test lint fix migrate revision check up down logs module

help:     ; @grep -E '^[a-z]+:' Makefile | sed 's/:.*#/ —/' | sed 's/: ;.*//'

setup:    ; uv sync && cp -n local.env.example local.env || true && uv run pre-commit install
dev:      ; uv run uvicorn app.main:app --reload
test:     ; uv run pytest -q
lint:     ; uv run ruff check . && uv run ruff format --check . && uv run mypy app
fix:      ; uv run ruff check --fix . && uv run ruff format .
migrate:  ; uv run alembic upgrade head
revision: ; uv run alembic revision --autogenerate -m "$(m)"
check:    ; uv run alembic check
up:       ; docker compose up -d postgres redis
down:     ; docker compose down
logs:     ; docker compose logs -f api

# Django's `startapp`, in nine lines. Usage: make module name=orders
module:   ; cp -r templates/module app/modules/$(name) && \
            grep -rl "sample\|Sample" app/modules/$(name) | \
            xargs sed -i 's/sample/$(name)/g; s/Sample/$(shell python3 -c "print('$(name)'.replace('_',' ').title().replace(' ',''))")/g' && \
            rm app/modules/$(name)/README.md && \
            echo "Created app/modules/$(name) — restart the server, it auto-mounts."
