# Fastango — Command Reference 📖

A single place for every command used in this project — local development, Docker, migrations, testing, code quality, and (most importantly) **how to add a new package when running under Docker with `pyproject.toml`**.

> 📌 **Key fact about this repo:** dependencies are declared in **two places** —
> [pyproject.toml](pyproject.toml) (Poetry, the source of truth) and
> [requirements.txt](requirements.txt) (what the [Dockerfile](Dockerfile) actually installs with `pip`).
> When you add a package, you must keep **both** in sync, then **rebuild the Docker image**.

---

## 📦 Package Management (Poetry / `pyproject.toml`)

| Command | Description |
| --- | --- |
| `poetry add <package>` | Add a runtime dependency to `[tool.poetry.dependencies]` in `pyproject.toml` and install it in your local venv. Example: `poetry add redis` |
| `poetry add <package>@^1.2.3` | Add a dependency pinned to a specific version constraint. Example: `poetry add celery@^5.4.0` |
| `poetry add "<package>[extra]"` | Add a dependency with extras. Example: `poetry add "uvicorn[standard]"` |
| `poetry add --group dev <package>` | Add a **dev-only** dependency to `[tool.poetry.group.dev.dependencies]` (linters, test tools). Example: `poetry add --group dev ruff` |
| `poetry remove <package>` | Remove a dependency from `pyproject.toml` and uninstall it |
| `poetry install` | Install everything declared in `pyproject.toml` (creates/uses `poetry.lock`) |
| `poetry lock` | Re-resolve and regenerate `poetry.lock` without installing |
| `poetry update <package>` | Bump a package to the latest version allowed by its constraint |
| `poetry show --tree` | Print the full dependency tree (great for debugging conflicts) |
| `poetry export -f requirements.txt --output requirements.txt --without-hashes` | Regenerate `requirements.txt` from `pyproject.toml` — **required in this repo** because Docker installs from `requirements.txt`. Needs the export plugin: `poetry self add poetry-plugin-export` |

### If you don't use Poetry locally (plain pip)

| Command | Description |
| --- | --- |
| `pip install <package>` | Install a package into the active venv |
| `pip install -r requirements.txt` | Install everything from `requirements.txt` |
| Manually edit `pyproject.toml` **and** `requirements.txt` | Add the package with its version to both files so venv, Docker, and teammates stay in sync |

---

## 🐳 Adding a Package While Using Docker (Step by Step)

Because the image is built from `requirements.txt` (see [Dockerfile:13-14](Dockerfile#L13-L14)), installing a package requires updating the TOML, syncing `requirements.txt`, and **rebuilding the image**. A package installed with `pip` inside a running container is lost the moment the container is recreated.

| Step | Command | Description |
| --- | --- | --- |
| 1 | `poetry add redis` | Declare the new package in `pyproject.toml` (source of truth). *(Or hand-edit the TOML if you don't use Poetry.)* |
| 2 | `poetry export -f requirements.txt --output requirements.txt --without-hashes` | Sync `requirements.txt` so the Docker build sees the new package. *(Or add the line `redis==5.x.x` manually.)* |
| 3 | `docker-compose build api` | Rebuild only the API image with the updated dependencies |
| 4 | `docker-compose up -d api` | Recreate the API container from the new image |
| 5 | `docker-compose exec api pip show redis` | Verify the package is installed inside the container |

**One-liner for steps 3–4:**
```bash
docker-compose up -d --build api
```

### Quick, temporary install (hotfix / experiment only ⚠️)

| Command | Description |
| --- | --- |
| `docker-compose exec api pip install <package>` | Installs into the **running** container only. Disappears on `docker-compose down` or rebuild — never rely on this; always follow the 5-step flow above afterwards |

---

## 💻 Local Development (Virtual Environment)

| Command | Description |
| --- | --- |
| `python3.13 -m venv --without-pip .venv` | Create the virtual environment (Python 3.13 recommended) |
| `source .venv/bin/activate` | Activate the venv |
| `curl -sSO https://bootstrap.pypa.io/get-pip.py && python3 get-pip.py && rm get-pip.py` | Bootstrap pip inside the venv |
| `pip install -r requirements.txt` | Install project dependencies |
| `pip install aiosqlite greenlet` | Extra packages required to run the test suite |
| `docker-compose up postgres redis -d` | Start only PostgreSQL + Redis in the background (app runs on host) |
| `alembic upgrade head` | Apply database migrations |
| `uvicorn app.main:app --reload` | Launch the dev server with hot reload → http://localhost:8000/docs |
| `export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"` | Override any setting from [local.env](local.env) via environment variable |

---

## 🐳 Docker & docker-compose

| Command | Description |
| --- | --- |
| `docker-compose up --build` | Build and start the full stack: `fastango_api`, `fastango_postgres`, `fastango_redis` |
| `docker-compose up -d` | Start the stack in the background (detached) |
| `docker-compose up -d --build api` | Rebuild and restart only the API service (use after dependency changes) |
| `docker-compose build api` | Rebuild the API image without starting it |
| `docker-compose logs -f` | Follow real-time logs from all services |
| `docker-compose logs -f api` | Follow logs from the API container only |
| `docker-compose exec api <command>` | Run any command inside the running API container |
| `docker-compose exec api bash` | Open an interactive shell inside the API container |
| `docker-compose ps` | List running services and their status |
| `docker-compose restart api` | Restart the API container |
| `docker-compose down` | Stop and remove all containers (data volumes kept) |
| `docker-compose down -v` | Stop everything **and wipe** PostgreSQL/Redis data volumes ⚠️ |

---

## 📐 Database Migrations (Alembic)

| Command (local venv) | Command (inside Docker) | Description |
| --- | --- | --- |
| `alembic revision --autogenerate -m "message"` | `docker-compose exec api alembic revision --autogenerate -m "message"` | Generate a new migration after changing any `models.py` |
| `alembic upgrade head` | `docker-compose exec api alembic upgrade head` | Apply all pending migrations |
| `alembic downgrade -1` | `docker-compose exec api alembic downgrade -1` | Roll back the last migration |
| `alembic current` | `docker-compose exec api alembic current` | Show the revision the database is currently at |
| `alembic history` | `docker-compose exec api alembic history` | List all migration revisions |

---

## 🧪 Testing

| Command | Description |
| --- | --- |
| `pytest -v` | Run the full test suite (in-memory SQLite via `aiosqlite`) |
| `pytest tests/<file>.py -v` | Run a single test file |
| `pytest -k "test_name" -v` | Run tests matching a name pattern |
| `docker-compose exec api pytest -v` | Run the test suite inside the Docker container |

---

## 🧹 Code Quality (pre-commit & Ruff)

| Command | Description |
| --- | --- |
| `pre-commit install` | One-time setup: install the Git hooks locally |
| `pre-commit run --all-files` | Run all hooks (whitespace, YAML, Ruff lint + format) on the entire repo |
| `ruff check . --fix` | Lint the codebase and auto-fix safe issues |
| `ruff format .` | Format all source code (replaces Black) |
| `git commit -m "wip" --no-verify` | Bypass the hooks for an emergency/WIP commit ⚠️ |

---

## 🏗️ Scaffolding a New Module (from `templates/module/`)

The repo ships a ready-made skeleton in [templates/module/](templates/module/) with all the layered files pre-wired (`apps.py`, `models.py`, `repositories.py`, `schemas.py`, `services.py`, `router.py`, `constants.py`) using `sample`/`Sample` placeholders. No CLI needed — copy, rename, done. Example below creates an **orders** module; replace `orders`/`Orders` with your module name.

| Step | Command | Description |
| --- | --- | --- |
| 1 | `cp -r templates/module app/modules/orders` | Copy the template into `app/modules/` under your module name |
| 2 | `grep -rl "sample\|Sample" app/modules/orders \| xargs sed -i 's/sample/orders/g; s/Sample/Orders/g'` | Replace every `sample`/`Sample` placeholder with your module name (lowercase **and** capitalized) |
| 3 | `rm app/modules/orders/README.md` | Remove the template's README from the copy |
| 4 | Restart the server (`uvicorn app.main:app --reload` or `docker-compose restart api`) | The registry auto-discovers the module and mounts it at `/api/v1/orders` — no registration step, no edits to `main.py` |

**After scaffolding** — if the module defines tables in `models.py`, generate and apply a migration:

```bash
alembic revision --autogenerate -m "add orders tables"
alembic upgrade head
```

(If the module owns no tables, just delete its `models.py`.)

---

## 🚀 Production

| Command | Description |
| --- | --- |
| `openssl rand -hex 32` | Generate a high-entropy `SECRET_KEY` |
| `alembic upgrade head` | Run migrations in CI/CD **before** routing traffic to new instances |
| `gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000` | Production server: 4 Uvicorn workers under Gunicorn (never use `--reload` in prod) |
