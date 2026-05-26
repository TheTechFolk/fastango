# Fastango — Developer Guide 📘

Welcome to the Fastango developer guide! This document explains how to configure, run, test, and deploy this project in local virtual environments, Docker containers, and production environments.

---

## 🏗️ Architecture & Modules Layout

Fastango uses a domain-driven, modular FastAPI design inspired by Django's structure.

* **Application Factory ([main.py](app/main.py))** — Boots the FastAPI instance, configures middleware/exception handlers, and delegates router + model registration to the module registry.
* **Module Registry ([core/registry.py](app/core/registry.py))** — Auto-discovers every package under `app/modules/`. For each module it (1) imports `models.py` so SQLAlchemy metadata is complete for Alembic, and (2) reads `apps.py` to mount the module's router under `/api/v1`. Replaces the legacy hand-edited `app/router.py` and `app/models.py`.
* **Exceptions Handler ([exceptions.py](app/exceptions.py))** — Configures all global server exception handlers and error trappers onto the application factory instance.
* **Middleware Configurator ([middleware.py](app/middleware.py))** — Configures and mounts global middleware layers (CORS, timing, request logging) onto the application.
* **Modules (`app/modules/`)** — Individual directories housing independent business features.

Each module follows a consistent layered pattern:
1. **Module Config (`apps.py`)** — Declares a `ModuleConfig` subclass with `name`, `router`, `prefix`, `tags`, plus optional `on_startup` / `on_shutdown` hooks. The registry discovers it automatically. Modules without an `apps.py` (e.g. `common`) are skipped for routing but their models are still imported.
2. **Database Schema (`models.py`)** — SQLAlchemy ORM table definitions. Optional if the module owns no tables.
3. **Query Layer (`repositories.py`)** — Async DB transactions and raw queries. Optional if the module is read-only or doesn't touch the DB.
4. **Validation (`schemas.py`)** — Pydantic request/response shapes.
5. **Business Logic (`services.py`)** — Use cases, validations, orchestrations.
6. **HTTP Controller (`router.py`)** — FastAPI path operations and dependency injections. The router is created with no prefix/tags — `apps.py` owns those.

### Adding a New Module

```bash
mkdir -p app/modules/orders
touch app/modules/orders/{__init__,apps,router,services,schemas,models,repositories}.py
```

Then in `app/modules/orders/apps.py`:
```python
from app.core.registry import ModuleConfig
from app.modules.orders.router import router

class OrdersConfig(ModuleConfig):
    name = "orders"
    router = router
    prefix = "/orders"
    tags = ["Orders"]
```

That's it. The registry picks it up on next boot — no edits to `main.py`, no central registry to maintain, no Alembic plumbing.

---

## 🛢️ Database Session Management (Request-Scoped ContextVar)

Fastango uses a modern, **request-scoped ContextVar pattern** to manage database sessions. Rather than forcing you to pass `db` manually through every route signature, service constructor, and helper function, Fastango manages this automatically in the background.

### How It Works Under the Hood
1. **Request Lifecycle**: When a new HTTP request arrives, a global FastAPI dependency (`inject_db_session_context`) opens an asynchronous SQLAlchemy session from our session factory.
2. **Context Binding**: The session is bound to an async-safe `contextvars.ContextVar` unique to the current request execution context.
3. **Automatic Cleanup**: When the request completes, the global dependency automatically commits any pending database transactions (or rolls back on error) and closes the session.

### How to use `get_db_session()` in your modules

#### 1. In a Route (Controller)
Routes do **not** need `Depends(get_db)` in their path operations! Keep your signatures focused exclusively on business inputs (like payloads and authentication tokens).

```python
# app/modules/orders/router.py
@router.post("")
async def create_order(payload: OrderCreateSchema):
    service = OrderService() # No need to pass db!
    return await service.create(payload)
```

#### 2. In a Service (Business Logic)
To perform database operations inside services or helper methods, import `get_db_session` from `app.database` and fetch the active session dynamically:

```python
# app/modules/orders/services.py
from app.database import get_db_session
from app.modules.orders.repositories import OrderRepository

class OrderService:
    async def create(self, data: OrderCreateSchema):
        # Fetch the active session out of thin air
        db = get_db_session()
        
        async with db.begin(): # Start a transaction block if needed
            order = Order(...)
            await OrderRepository.create(db, order)
```

### Writing Tests with `get_db_session()`
The `ContextVar` binder dynamically resolves standard FastAPI dependencies. When writing tests, our test client's `dependency_overrides[get_db]` will override the base session automatically, meaning your test database sessions work **flawlessly out of the box** without any special configuration.

```python
# conftest.py (automatic override handled in standard pytest fixtures)
app.dependency_overrides[get_db] = override_get_db
```

---

## 🔑 Environment Configuration

Fastango uses Pydantic Settings (`BaseSettings`) to manage configuration centrally.

### How Settings are Loaded
1. **Local Development Default**: In local dev, Pydantic is configured to read directly from [local.env](file:///home/thededar/Downloads/Workspace/fastango_v1/local.env) at the root of the project.
2. **Overriding Settings**: You can override any configuration value by exporting standard environment variables on your system, or defining them in your shell:
   ```bash
   export DATABASE_URL="postgresql+asyncpg://user:pass@host:5432/dbname"
   ```
3. **Production Mode**: In production containers, Pydantic Settings automatically extracts all variables from the container shell/host environment, completely bypassing file config dependencies for security.

---

## 💻 Running Locally (Virtual Environment)

Running the project directly in your host OS is recommended for rapid development.

### 1. Create a Python Virtual Environment
We recommend utilizing **Python 3.13** (to avoid source wheel compilation errors on experimental Python runtimes like 3.14):
```bash
python3.13 -m venv --without-pip .venv
source .venv/bin/activate
curl -sSO https://bootstrap.pypa.io/get-pip.py && python3 get-pip.py && rm get-pip.py
```

### 2. Install Development Dependencies
```bash
pip install -r requirements.txt
pip install aiosqlite greenlet  # Required to run the test suite
```

### 3. Spin Up Auxiliary Services (Docker)
Instead of installing PostgreSQL and Redis directly, spin them up as background containers:
```bash
docker-compose up postgres redis -d
```

### 4. Run Migrations & Launch App
```bash
alembic upgrade head
uvicorn app.main:app --reload
```
Your service will be available at: http://localhost:8000/docs

---

## 🐳 Running with Docker

You can run the entire Fastango stack inside Docker networks using the supplied `docker-compose.yml` config.

### 1. Build and Start the Stack
This boots up the FastAPI container (`fastango_api`), PostgreSQL (`fastango_postgres`), and Redis (`fastango_redis`):
```bash
docker-compose up --build
```

### 2. Run Database Migrations Inside Docker
To apply your Alembic migrations onto the PostgreSQL container, run:
```bash
docker-compose exec api alembic upgrade head
```

### 3. View Logs & Tear Down
* View real-time output: `docker-compose logs -f`
* Stop services: `docker-compose down`
* Stop and wipe data volumes: `docker-compose down -v`

---

## 📐 Database Migrations (`alembic`)

Alembic tracks schema changes. All migration version scripts reside in `alembic/versions/`.

### 1. Autogenerate a Migration
When you modify or add any SQLAlchemy models in your modules (e.g. `app/modules/auth/models.py`), generate a new version revision:
```bash
# In local venv:
alembic revision --autogenerate -m "describe changes here"

# In Docker:
docker-compose exec api alembic revision --autogenerate -m "describe changes here"
```

### 2. Apply Migrations
Update your database schema to the latest version:
```bash
# In local venv:
alembic upgrade head

# In Docker:
docker-compose exec api alembic upgrade head
```

### 3. Rollback Migrations
Rollback the last migration schema change:
```bash
# In local venv:
alembic downgrade -1

# In Docker:
docker-compose exec api alembic downgrade -1
```

---

## 🧪 Testing Guidelines

Fastango includes an integration and unit testing framework built around `pytest` and `httpx.AsyncClient`. It runs against an **in-memory SQLite** test database via `aiosqlite` for isolated, ultra-fast validation.

### Run the Test Suite
Ensure the virtual environment is active and run:
```bash
pytest -v
```

---

## 🚀 Production Guidelines

When moving your application to a production cluster:

### 1. Security Checklist
* Generate a high-entropy cryptographically secure `SECRET_KEY` (e.g. `openssl rand -hex 32`).
* Restrict CORS settings (`CORS_ORIGINS`) to only trust specific frontend domains.

### 2. Running Migrations in CI/CD
Always run database migrations as a block step in your deployment pipeline *before* swapping traffic to the new API instances:
```bash
alembic upgrade head
```

### 3. Deployment Server Execution
Do not use `--reload` in production. Run with a production server configuration, utilizing multiple worker threads (e.g., Gunicorn running Uvicorn workers):
```bash
gunicorn app.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000
```

---

## 🔐 Core Endpoints Overview

* **Health Check**: `GET /health`
* **Registration**: `POST /api/v1/auth/register`
* **Login**: `POST /api/v1/auth/login`
* **Landing Home**: `GET /api/v1/home`
* **User Profile**: `GET /api/v1/profile`
