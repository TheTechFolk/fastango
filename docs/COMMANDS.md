# Fastango — Command Reference

> **Dependencies live in one place**: [pyproject.toml](../pyproject.toml), locked
> by [uv.lock](../uv.lock). The local venv, CI and the Docker image all install
> from that lockfile, so there is nothing to keep in sync by hand.
> **There is no `requirements.txt`. Do not recreate it.**

See [README.md](../README.md) for the quickstart and [GUIDE.md](GUIDE.md) for the architecture guide.
Most commands below have a `make` shortcut (`make help` lists them).

---

## Setup

| Command | Description |
| --- | --- |
| `make setup` | `uv sync`, copy `local.env.example` → `local.env`, install pre-commit hooks |
| `make up` | Start postgres + redis (bound to 127.0.0.1) |
| `make migrate` | `alembic upgrade head` |
| `make dev` | Run uvicorn with `--reload` |
| `make down` | Stop the compose stack |

Install uv once: `curl -LsSf https://astral.sh/uv/install.sh | sh`

---

## Packages (uv)

| Command | Description |
| --- | --- |
| `uv sync` | Create/refresh `.venv` from `uv.lock` — runtime **and** dev dependencies |
| `uv sync --frozen` | The same, but fail rather than update the lockfile. What CI runs |
| `uv sync --no-dev` | Runtime only. What the Docker image installs |
| `uv add <pkg>` | Add a runtime dependency, resolve, install |
| `uv add "<pkg>>=1.2,<2"` | Add with an explicit constraint |
| `uv add --dev <pkg>` | Add to the `dev` group — never shipped to production |
| `uv remove <pkg>` | Remove and uninstall |
| `uv lock --upgrade-package <name>` | Bump one package within its constraint |
| `uv tree` | Print the dependency tree |
| `uv run <cmd>` | Run inside the project environment without activating it |

**Do not use `pip install`.** It writes into the venv without touching
`pyproject.toml` or `uv.lock`, so the change is invisible to CI, to Docker, and
to everyone else.

Adding a package while using Docker means rebuilding the image — the image
installs from the lockfile, so a `pip install` inside a running container is
lost the moment it is recreated:

```bash
uv add redis && docker compose up -d --build api
```

---

## Modules

| Command | Description |
| --- | --- |
| `make module name=orders` | Scaffold `app/modules/orders/` from `templates/module/` |

Restart the server — it is auto-discovered and mounted at
`/private/api/v1/orders`. There is no registration step.

To disable a module without deleting it, set `DISABLED_MODULES=["orders"]`.
Its models stay imported so migrations remain complete.

---

## Migrations

| Command | Description |
| --- | --- |
| `make migrate` | Apply all pending migrations |
| `make revision m="add orders"` | Autogenerate a revision from model changes |
| `make check` | `alembic check` — fail if models drifted from migrations |
| `uv run alembic downgrade -1` | Roll back one revision |
| `uv run alembic history` | Show the revision graph |
| `uv run alembic current` | Show the applied revision |

**Always read a generated revision before committing it.** Autogenerate does not
detect table or column renames — it emits a drop plus a create, which is data
loss. And **migrations are committed**; a template that cannot build its own
schema is not a template.

---

## Tests & quality

| Command | Description |
| --- | --- |
| `make test` | `pytest -q` |
| `uv run pytest -q --cov --cov-report=term-missing` | With coverage |
| `uv run pytest tests/modules/auth -v` | One module |
| `uv run pytest -k "refresh"` | By name |
| `make lint` | ruff check + ruff format --check + mypy |
| `make fix` | ruff --fix + ruff format |
| `uv run pre-commit run --all-files` | Every hook against the whole tree |

---

## Docker

| Command | Description |
| --- | --- |
| `docker compose up -d --build` | Build and start everything |
| `make logs` | Follow the API logs |
| `docker compose exec api bash` | Shell into the API container |
| `docker compose exec api alembic upgrade head` | Migrate inside the container |
| `docker compose down -v` | Stop and **delete the volumes** |

---

## Health

| Endpoint | Purpose |
| --- | --- |
| `GET /health` | Liveness. Touches nothing — a DB outage must drain the container, not kill it |
| `GET /health/ready` | Readiness. Pings the database. **This is the one to route on** |

---

## Routes

| Prefix | Auth |
| --- | --- |
| `/public/api/v1/...` | none |
| `/private/api/v1/...` | Bearer access token |

```bash
TOKEN=$(curl -s -X POST localhost:8000/public/api/v1/auth/login \
  -H 'content-type: application/json' \
  -d '{"email":"you@example.com","password":"..."}' | jq -r .data.access_token)

curl localhost:8000/private/api/v1/auth/me -H "Authorization: Bearer $TOKEN"
```

`/docs` is served in development only.
