# Fastango 🚀

Fastango is a Django-inspired modular project boilerplate built on top of FastAPI. It lets you build large, scalable FastAPI projects using pluggable mini-apps, similar to Django apps, with optional DRM, access control, and security-first design.

⚡ FastAPI speed · 🧩 Django-like apps · 🔐 Built-in security mindset

---

## 🚀 Why Fastango?
FastAPI is fast and modern, but as projects grow, managing routes, services, permissions, and business logic can become messy. Django solves this with its app-based architecture — Fastango brings that idea to FastAPI, without sacrificing performance or flexibility.

Fastango is designed for:
* Large FastAPI backends
* Multi-tenant systems
* DRM / protected APIs
* Research & production-ready systems
* Teams who love Django’s structure but need FastAPI’s speed

---

## ✨ Key Features
* 🧩 **Django-like Mini Apps**: Each feature lives in its own self-contained app.
* 🔌 **Pluggable Architecture**: Enable/disable apps dynamically.
* 🔐 **DRM & Access Control Ready**: Built-in hooks for license checks, permissions, and policies.
* ⚡ **FastAPI Native**: Fully compatible with FastAPI dependencies, routers, and async.
* 🏗️ **Clean Project Structure**: Opinionated but flexible layout for long-term maintainability.
* 🧪 **Test-Friendly**: Easy unit and integration testing per app.

---

## 🏗️ Project Structure

```
fastango_v1/
├── app/
│   ├── main.py              # Application factory (with global request ContextVar hooks)
│   ├── config.py            # Pydantic BaseSettings (loads local.env)
│   ├── database.py          # Async SQLAlchemy engine + request-scoped session ContextVar helper
│   ├── exceptions.py        # Centralized exception handlers registration
│   ├── middleware.py        # Centralized middleware configurator (CORS & TrustedHost)
│   └── core/
│       ├── registry.py      # Module auto-discovery (router + model registration)
│       ├── security.py      # JWT + bcrypt
│       ├── responses.py     # Standard response envelope
│       ├── exceptions.py    # Custom exception hierarchy
│       ├── audit.py         # Async request audit logger
│       └── storage.py       # AWS S3 service
│   └── modules/             # Each module declares an apps.py ModuleConfig
│       ├── common/          # Shared base models & enums (no router)
│       ├── auth/            # Shared authentication (register & login)
│       ├── home/            # General landing overview / dashboard
│       └── profile/         # User profile management
├── tests/
│   ├── conftest.py          # Async pytest fixtures (in-memory DB)
│   └── modules/             # Integration tests per module
├── alembic/                 # Database migrations
├── requirements.txt
├── pyproject.toml
├── docker-compose.yml
└── local.env
```

---

## 🚀 Quick Start

### 1. Install dependencies

Create a virtual environment and install the required modules:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Install pre-commit hooks

```bash
pre-commit install
```

### 3. Start the database

```bash
docker-compose up postgres redis -d
```

### 4. Run migrations

```bash
alembic upgrade head
```

### 5. Run the server

```bash
uvicorn app.main:app --reload
```

Visit: http://localhost:8000/docs

---

## 🐳 Docker (Full Stack)

```bash
docker-compose up --build
```

---

## 🧪 Running Tests

Ensure test dependencies are installed and execute pytest:

```bash
pip install aiosqlite greenlet
pytest -v
```

---

## 📐 Architecture Layers

Each leaf module follows the same layered pattern:

| Layer | File | Responsibility |
|---|---|---|
| Module Config | `apps.py` | `ModuleConfig` declaring name, router, prefix, tags, lifespan hooks |
| Database Schema | `models.py` | SQLAlchemy ORM table definitions (optional) |
| Query Layer | `repositories.py` | Async DB read/write operations (optional) |
| Validation | `schemas.py` | Pydantic request/response shapes |
| Business Logic | `services.py` | Use-cases, transactions, orchestration |
| HTTP Controller | `router.py` | FastAPI endpoints — no prefix/tags (owned by `apps.py`) |

Modules are auto-discovered by [app/core/registry.py](app/core/registry.py): drop a folder with an `apps.py` and it mounts automatically. No central registry to edit.

---

## 🔐 API Endpoints

### 🔑 Authentication
* `POST /api/v1/auth/register` — Register a new user account
* `POST /api/v1/auth/login` — Authenticate credentials and get JWT token pair

### 🏠 Home
* `GET  /api/v1/home` — Simple landing welcome data

### 👤 Profile
* `GET  /api/v1/profile` — Fetch active authenticated user profile details

### 🏥 Health
* `GET  /health` — Returns application status and health checks
