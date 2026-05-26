# Fastango 🚀

> **Fastango** — *Bring Django's structure to FastAPI, without slowing it down.*

 A production-ready FastAPI boilerplate that mirrors Django's clean, modular, domain-driven architecture with native async performance.

---

## 🏗️ Project Structure

```
fastango_v1/
├── app/
│   ├── main.py              # Application factory
│   ├── config.py            # Pydantic BaseSettings (loads local.env)
│   ├── database.py          # Async SQLAlchemy engine + session dependency
│   ├── exceptions.py        # Centralized exception handlers registration
│   ├── middleware.py        # Centralized middleware configurator
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

## 🚀 Quick Start

### 1. Install dependencies

Create a virtual environment and install the required modules:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Start the database

```bash
docker-compose up postgres redis -d
```

### 3. Run migrations

```bash
alembic upgrade head
```

### 4. Run the server

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
- `POST /api/v1/auth/register` — Register a new admin account
- `POST /api/v1/auth/login` — Authenticate credentials and get JWT token pair

### 🏠 Home
- `GET  /api/v1/home` — Simple landing welcome data

### 👤 Profile
- `GET  /api/v1/profile` — Fetch active authenticated user profile details

### 🏥 Health
- `GET  /health` — Returns application status and health checks
# fastango
