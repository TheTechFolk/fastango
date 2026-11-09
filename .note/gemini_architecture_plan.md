# FastAPI Template Architecture Review & Blueprint

---

## Executive Summary

This document provides a deep architectural comparison between two codebases:
1. **Current Template Project (`fastango_v1`)**: An initial attempt at translating a large modular Django/DRF architecture into FastAPI, featuring auto-discovered module directories, layered design (`models`, `repositories`, `services`, `schemas`, `router`, `apps`), and basic infrastructure.
2. **Reference Project (`argus-backend`)**: A hardened, production-grade evolution that resolves critical security oversights, introduces default-deny authentication routing, centralized correlation IDs, unified exception enveloping, CPU offloading for cryptography, and `uv`-native containerization.

### Core Architectural Finding
The modular "Django-app" pattern in FastAPI works exceptionally well **when paired with auto-discovery, explicit transaction boundaries, and clear public/private route conventions**. However, FastAPI is not Django:
* Django relies on heavy global state, metaclass registry magic, and tight ORM coupling.
* FastAPI excels through explicit dependency injection, Pydantic type contracts, ASGI composability, and async concurrency.

The goal of this template is **Option C: A Hybrid Modular Architecture**—combining framework-level core infrastructure (`app/core/`, `app/config.py`, `app/database.py`) with self-contained, domain-driven feature modules (`app/modules/<feature>/`), eliminating repetitive boilerplate while maintaining strict architectural boundaries.

---

## 1. Analysis of the Current Project (`fastango_v1`)

```
fastango_v1/
├── app/
│   ├── config.py              # Pydantic BaseSettings
│   ├── database.py            # Async SQLAlchemy engine + ContextVar session
│   ├── exceptions.py          # Minimal catch-all exception handler
│   ├── main.py                # FastAPI app initialization & auto-discovery boot
│   ├── middleware.py          # CORS, TrustedHost, basic timing
│   ├── core/                  # Shared utilities (audit, rate_limit, registry, responses, security, storage)
│   └── modules/               # Domain modules (auth, common, home, profile)
├── alembic/                   # Migrations
├── tests/                     # Pytest suite with in-memory SQLite
└── pyproject.toml             # Poetry config
```

### What Is Good?
* **Auto-Discovery Module Registry (`app/core/registry.py`)**: Walking `app/modules/*` dynamically and mounting routers defined in `apps.py` (`ModuleConfig`) removes manual route-wiring boilerplate.
* **Uncommitted-Write Guard (`app/database.py`)**: SQLAlchemy event listeners (`after_flush`, `after_commit`, `after_rollback`) that fail fast if a service mutates database entities without an explicit `async with db.begin():` block.
* **Feature App Modularity (`app/modules/`)**: High cohesion per domain—each module groups its own models, schemas, services, repositories, and routes.
* **Automated Alembic Discovery**: `import_all_models()` dynamically loads all module models so Alembic migrations stay accurate without manually updating `env.py`.

---

### What Is Unnecessarily Complicated or Flawed?

#### 1. Dead Pass-Through Abstractions
`app/modules/profile/repositories.py` is a 15-line file that does nothing but forward calls:
```python
class ProfileRepository:
    @staticmethod
    async def get_profile_by_code(db: AsyncSession, user_code: uuid.UUID) -> AdminAuth | None:
        return await AdminAuthRepository.get_by_admin_code(db, user_code)
```
`app/modules/profile/models.py` contains only comments. Creating empty or pass-through files just to fulfill a rigid 6-file-per-module rule creates unnecessary mental overhead.

#### 2. Service Return Pattern (`tuple[data, str]`)
Services return Go-style tuples: `tuple[dict | None, str]`. Routers are forced to write boilerplate checks on every endpoint:
```python
# app/modules/auth/router.py
data, msg = await service.register(payload)
if data is None:
    raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=msg)
return success_response(data=data, message=msg)
```
This bypasses FastAPI's exception-handling pipeline, is prone to unchecked error returns, and requires manual HTTP status code management inside route handlers.

#### 3. Database Connection Checkout on Non-DB Routes
In `app/main.py`:
```python
app = FastAPI(
    ...
    dependencies=[Depends(inject_db_session_context)],
)
```
Attaching the DB session injector as a global application dependency forces every single incoming request—including `/health` liveness probes and CORS `OPTIONS` preflights—to acquire and release a connection from the SQLAlchemy connection pool.

---

### What Is Missing or Dangerous?

| Area | Issue in `fastango_v1` | Risk / Impact |
| :--- | :--- | :--- |
| **Exception Handling** | `app/core/exceptions.py` defines `FastangoException`, `NotFoundException`, `UnauthorizedException`, but `app/exceptions.py` only registers a handler for `Exception`. | Any custom exception raised in business logic falls through to the generic 500 handler. `RequestValidationError` (422) is not enveloped. |
| **Auth Security Bypass** | `app/core/security.py` returns a hardcoded mock UUID if `APP_ENV in ("local", "test", "testing")` and no Bearer token is provided. | A staging or production environment misconfigured as `APP_ENV=local` completely disables authentication across all protected endpoints. |
| **Blocking Cryptography** | `hash_password()` and `verify_password()` run `bcrypt` synchronously directly on the async event loop. | Bcrypt at work factor 12 takes ~300ms of pure CPU time. During this time, the entire worker event loop is blocked, dropping throughput for all concurrent users. |
| **JWT Type Confusion** | `decode_token()` does not validate the `type` claim or enforce required claims (`exp`, `sub`, `iat`). | A refresh token can be passed to protected endpoints in place of an access token. Tokens without expiration never expire. |
| **Dependency Management** | `pyproject.toml` lists `python-jose` and `passlib` (unmaintained on Python 3.12+), while code imports `jwt` (PyJWT) and `bcrypt`. | `poetry install` creates mismatched environments with deprecated transitive dependencies. |
| **Observability** | No request correlation IDs (`X-Request-ID`). `app/core/audit.py` is an uninvoked stub. | 500 errors in logs cannot be correlated with user bug reports. |

---

## 2. Analysis of the Reference Project (`argus-backend`)

```
argus-backend/
├── app/
│   ├── config.py              # Hardened Pydantic settings with validators
│   ├── database.py            # SQLAlchemy 2.0 DeclarativeBase, pool recycle & SQLite guards
│   ├── exceptions.py          # Complete exception hierarchy mapping to standard envelope
│   ├── logging_config.py      # Request-ID injected root logger setup
│   ├── main.py                # Graceful lifespan shutdown, dual health probes
│   ├── middleware.py          # Default-deny auth, X-Request-ID, security headers
│   ├── core/                  # Framework core (context, security, decorators, registry, rate_limit)
│   └── modules/               # auth, common, synthetic, scoring, evaluation, governance, ingestion, detection, analysis
├── alembic/                   # Versioned database migrations
├── tests/                     # Unit, integration, API, security tests with SQLite FK pragmas
├── Dockerfile                 # Multi-stage uv build with non-root runtime
└── pyproject.toml             # uv-managed single source of truth
```

### Why This Structure Works

#### 1. Default-Deny Route Architecture
`argus-backend` splits module routing into `router` (mounted at `/private/api/v1`) and `public_router` (mounted at `/public/api/v1`).
```python
# app/modules/auth/apps.py
class AuthConfig(ModuleConfig):
    name = "auth"
    prefix = "/auth"
    tags = ["Auth"]
    public_router = public_router   # /public/api/v1/auth/login, /register, /refresh
    router = private_router         # /private/api/v1/auth/me
```
* **Security by Default**: A newly created module with standard `router` is private by default. Exposing a public route requires an explicit decision to use `public_router`.
* **Zero Route-Level Decorator Sprawl**: Developers don't have to remember to add `@requires_auth` or `Depends(get_current_user)` to every endpoint.

#### 2. CPU Offloading for Cryptography
`app/modules/auth/utils.py` uses `anyio.to_thread.run_sync` to run password hashing outside the async event loop:
```python
async def ahash_password(plain_password: str) -> str:
    return await anyio.to_thread.run_sync(hash_password, plain_password)
```
Additionally, `_DUMMY_HASH` constant-time verification prevents account enumeration via timing side-channels.

#### 3. Exception-Driven Control Flow & Centralized Enveloping
Instead of returning tuples, services raise subclasses of `ArgusException` (`NotFoundException`, `ValidationException`, `UnauthorizedException`).
* Each exception defines its own `status_code` and default `message`.
* `app/exceptions.py` catches all exceptions (`ArgusException`, `RequestValidationError`, `RateLimitExceeded`, `IntegrityError`, `OperationalError`, `SQLAlchemyError`, `StarletteHTTPException`) and maps them to a consistent JSON envelope:
```json
{
  "error": true,
  "message": "Resource not found.",
  "data": null
}
```

#### 4. Diagnostic Traceability (`X-Request-ID`)
`app/core/context.py` maintains `request_id_ctx` (`ContextVar`). `RequestIdFilter` in `app/logging_config.py` injects `request_id` into every log record emitted by application or third-party loggers, and the middleware exposes `X-Request-ID` in the response header.

#### 5. Modern Packaging (`uv`)
Uses `pyproject.toml` with `[project]` standard (PEP 621), `uv.lock`, and multi-stage Docker builds. Dev tools (`pytest`, `ruff`, `mypy`, `debugpy`) are isolated into dependency groups and excluded from the production image.

---

### What Is Project-Specific in `argus-backend` (Must NOT be in Base Template)
1. **ML Inference Pipeline**: ONNX Runtime, Tokenizers, Wolf-Defender weights download in Dockerfile.
2. **Domain-Specific Modules**: `synthetic/`, `scoring/`, `evaluation/`, `governance/`, `ingestion/`, `detection/`, `analysis/`.
3. **Synthetic Data Generators & Rules Engines**: YAML rule loaders, Faker generator configs, scoring weight matrices.

---

## 3. Side-by-Side Architectural Comparison

| Architectural Area | Project 1 (`fastango_v1`) | Project 2 (`argus-backend`) | Recommended Ideal Approach |
| :--- | :--- | :--- | :--- |
| **Package Management** | Poetry with outdated / conflicting libraries (`python-jose`, `passlib`). | `uv` + `pyproject.toml` (PEP 621) with lockfile and dependency groups. | **`uv` + `pyproject.toml`**: 10-100x faster, strictly reproducible, standardized. |
| **Project Structure** | Hybrid with loose conventions; empty placeholder files. | Hybrid modular with strict public/private route roots. | **Hybrid Modular (Core + Feature Modules)** with clean module scaffolding. |
| **App / Module Registry** | Discovers `apps.py` and mounts under `/api/v1/<prefix>`. | Discovers `apps.py`, mounts `router` at `/private/api/v1` and `public_router` at `/public/api/v1`. | **Dual-Mount Module Registry** (`/api/v1` default-deny private root + `/api/v1/public` or `/public/api/v1`). |
| **Configuration** | `pydantic-settings` BaseSettings, loose types. | `pydantic-settings` with strict validators (rejects weak keys, validates CORS, environment literals). | **Hardened `pydantic-settings`**: Literal environments, startup secret strength enforcement, safe CORS rules. |
| **Database ORM** | SQLAlchemy legacy `declarative_base()`, basic async session. | SQLAlchemy 2.0 `class Base(DeclarativeBase)`, `pool_recycle`, engine options adjusted for SQLite. | **SQLAlchemy 2.0 `DeclarativeBase`** + explicit transactions + uncommitted write guard + `engine.dispose()` on shutdown. |
| **DB Session Scope** | Global dependency on `FastAPI(dependencies=[...])` (runs on `/health`). | Global dependency on `FastAPI(dependencies=[...])` (runs on `/health`). | **Scoped Dependency**: Inject `get_db` on API router / route level, exempting `/health` and static assets. |
| **API Envelope & Routes** | Manual `success_response()` / `error_response()` calls in handlers. | `@api_response()` decorator stripping annotations + centralized exception handlers. | **Native Response Models + Unified Exception Handlers**: Native FastAPI `response_model=APIResponse[T]` for docs precision. |
| **Service Layer** | Returns `tuple[data, error_str]`. Routers check `if data is None: raise`. | Services raise `ArgusException` subclasses. Return clean domain data models. | **Exception-Driven Services**: Raise typed domain exceptions (`NotFoundException`, `ValidationException`). Handlers stay clean. |
| **Repository Layer** | Static methods on classes; pass-through wrappers in some modules. | Static/module methods on repository classes; shared SQL dialect helpers in `common`. | **Pragmatic Repositories**: Pure async functions or simple classes for DB operations. Delete empty pass-through repos. |
| **Authentication** | JWT with HS256, sync bcrypt, unsafe dev mock fallback. | JWT with claim enforcement, async bcrypt via thread pool, constant-time dummy hash, no dev bypass. | **Async Bcrypt + Hardened JWT**: Thread-offloaded hashing, constant-time dummy verify, strict claim check, real test tokens. |
| **Error Handling** | Incomplete: custom exceptions fall through to 500, unhandled 422. | Comprehensive: maps `ArgusException`, `RequestValidationError`, `IntegrityError` (409), `OperationalError` (503), 429. | **Comprehensive Enveloped Exception Handlers**: Consistent JSON envelope + `X-Request-ID` across every HTTP status. |
| **Logging & Tracing** | Standard python `logging`, no correlation ID. | Request-ID injected into root logging filter, `X-Request-ID` header, request timing. | **Structured Logging with ContextVar Request ID** (`logging` filter + optional JSON format for production). |
| **Testing Architecture** | Pytest with in-memory SQLite, deprecated event loop fixture. | Pytest + SQLite with `PRAGMA foreign_keys=ON`, `request_session` fixture, `auth_header()` helpers, security tests. | **Isolated Async Pytest Suite**: SQLite with FK enforcement, real token generation fixtures, zero auth bypasses. |
| **Docker / Deploy** | Single-stage Dockerfile running as root. | Multi-stage Dockerfile with `uv`, non-root user, healthchecks, loopback-bound ports in Compose. | **Multi-Stage Non-Root Dockerfile** + hardened Compose with healthchecks & loopback port bindings. |

---

## 4. Architectural Design: The Ideal FastAPI Template

### The Organizational Debate: Layer vs Feature vs Hybrid

```
┌────────────────────────────────────────────────────────────────────────┐
│                        ARCHITECTURAL TAXONOMY                          │
├────────────────────────────────┬───────────────────────────────────────┤
│ Option A: Layer-Based          │ Option B: Pure Feature-Based          │
│ app/                           │ app/                                  │
│ ├── routers/ (all endpoints)   │ ├── users/ (models, views, logic)     │
│ ├── services/ (all logic)      │ ├── billing/ (models, views, logic)   │
│ ├── models/ (all ORM tables)   │ ├── auth/ (models, views, logic)      │
│ └── schemas/ (all DTOs)        │ └── (No shared core or boundary)      │
│ ❌ Fails at scale: merge       │ ❌ Fails at scale: duplicate configs, │
│    conflicts, scattered domain │    scattered middleware, circular refs│
├────────────────────────────────┴───────────────────────────────────────┤
│ Option C: Hybrid Modular (RECOMMENDED)                                 │
│ app/                                                                  │
│ ├── core/          <- Stable framework infrastructure (Security,      │
│ │                     Context, Exceptions, Registry, Responses)        │
│ ├── database.py    <- Engine, Base, Session Lifecycle                 │
│ ├── config.py      <- Validated App Settings                           │
│ └── modules/       <- Self-contained pluggable mini-apps               │
│     ├── auth/      <- (apps.py, models.py, schemas.py, services.py)   │
│     ├── users/     <- (apps.py, models.py, schemas.py, services.py)   │
│     └── common/    <- (Shared base models, enums, reusable validators) │
│ ✔ High cohesion per domain + robust shared infrastructure             │
└────────────────────────────────────────────────────────────────────────┘
```

### Why Option C (Hybrid Modular) Wins
1. **Django-like Mental Model**: Every feature is packaged inside its own directory under `app/modules/<feature>/`. A developer working on `users` never touches `billing` or `auth` files.
2. **FastAPI-Native Execution**: Core handles ASGI middleware, lifecycle hooks, exception envelopes, and security dependencies cleanly.
3. **Pluggable & Toggleable**: Modules declare `apps.py` (`ModuleConfig`). Features can be enabled or disabled via configuration (`ENABLED_MODULES`, `DISABLED_MODULES`) without breaking Alembic migrations.

---

## 5. Complete Recommended Directory Structure

```text
fastango/
├── .github/
│   └── workflows/
│       └── ci.yml                      # CI pipeline (lint, type-check, test, migration-check)
├── alembic/
│   ├── versions/                       # Migration revisions
│   ├── env.py                          # Auto-imports all module models
│   └── script.py.mako                  # Migration template
├── app/
│   ├── __init__.py
│   ├── config.py                       # Hardened Pydantic settings with validators
│   ├── database.py                     # SQLAlchemy 2.0 engine, Base, session dependencies
│   ├── exceptions.py                   # Centralized exception handlers (envelopes 400, 401, 403, 404, 409, 422, 429, 500, 503)
│   ├── logging_config.py               # Structured logging setup with X-Request-ID filter
│   ├── main.py                         # Application factory, lifespan, middleware wiring, module mounting
│   ├── middleware.py                   # Security headers, CORS, request ID, audit timing, default-deny auth
│   ├── core/                           # Framework infrastructure (zero business logic)
│   │   ├── __init__.py
│   │   ├── constants.py                # Global message constants, token types, default claims
│   │   ├── context.py                  # ContextVar request correlation ID helpers
│   │   ├── exceptions.py               # Base FastangoException hierarchy (NotFound, Validation, etc.)
│   │   ├── pagination.py               # Standardized PaginatedResponse[T] and pagination params
│   │   ├── rate_limit.py               # slowapi Limiter instance + Redis backend integration
│   │   ├── registry.py                 # ModuleConfig base class + auto-discovery engine
│   │   ├── responses.py                # Generic APIResponse[T] Pydantic envelope model
│   │   ├── security.py                 # JWT decoding, Bearer scheme, role guards (verify only)
│   │   └── storage.py                  # Optional S3/Storage interface with async client
│   └── modules/                        # Domain feature modules (pluggable mini-apps)
│       ├── __init__.py
│       ├── common/                     # Cross-module shared types (no apps.py, never mounted as router)
│       │   ├── __init__.py
│       │   ├── enums.py                # Global enums (RoleType, Environment, etc.)
│       │   ├── models.py               # TimeStampedBase, CommonFieldBase (abstract ORM mixins)
│       │   └── schemas.py              # Annotated reusable field types (EmailField, PasswordField)
│       ├── auth/                       # Authentication & session foundation
│       │   ├── __init__.py
│       │   ├── apps.py                 # AuthConfig: mounts public login/register/refresh & private /me
│       │   ├── constants.py            # Auth-specific messages & error strings
│       │   ├── models.py               # UserAuth ORM table
│       │   ├── repositories.py         # DB operations for auth records
│       │   ├── router.py               # public_router (login, register, refresh) & private_router (/me)
│       │   ├── schemas.py              # LoginSchema, RegisterSchema, TokenResponse, MeResponse
│       │   ├── services.py             # AuthService, TokenRefreshService, AccountService
│       │   └── utils.py                # Bcrypt async hashing, token minting (issues credentials)
│       └── users/                      # User management & profile domain
│           ├── __init__.py
│           ├── apps.py                 # UsersConfig (mounted under /private/api/v1/users)
│           ├── constants.py            # User module constants
│           ├── models.py               # UserProfile ORM table
│           ├── repositories.py         # DB queries for user profiles
│           ├── router.py               # Profile CRUD endpoints
│           ├── schemas.py              # UserProfileIn, UserProfileOut
│           └── services.py             # UserProfileService
├── docker/
│   ├── Dockerfile                      # Multi-stage uv build, non-root user
│   ├── docker-compose.yml              # Local dev stack (API, PostgreSQL, Redis)
│   └── docker-compose.debug.yml        # Debugpy overlay for IDE attach
├── scripts/
│   ├── startapp.py                     # CLI tool: `python scripts/startapp.py <module_name>`
│   └── wait_for_db.py                  # DB readiness probe before running migrations
├── templates/
│   └── module/                         # Skeleton copied by startapp.py
│       ├── README.md
│       ├── __init__.py
│       ├── apps.py
│       ├── constants.py
│       ├── models.py
│       ├── repositories.py
│       ├── router.py
│       ├── schemas.py
│       └── services.py
├── tests/
│   ├── __init__.py
│   ├── conftest.py                     # Fixtures: db_session, anon_client, client, admin_client
│   ├── core/                           # Framework tests
│   │   ├── test_config.py              # Settings validation & secret key rejection tests
│   │   ├── test_middleware.py          # Public/private route gating & security header tests
│   │   ├── test_registry.py            # Auto-discovery & module enable/disable tests
│   │   └── test_security.py            # Token decode, claim enforcement, algorithm tests
│   └── modules/                        # Per-module test suites
│       ├── test_auth.py                # Login, register, refresh, timing resistance tests
│       └── test_users.py               # User profile CRUD & permission tests
├── .env.example                        # Documented environment template
├── .gitignore                          # Ignores .env, .venv, pycache, coverage, sqlite db
├── .pre-commit-config.yaml             # Ruff, mypy, trailing-whitespace, check-yaml
├── alembic.ini                         # Alembic database configuration
├── Makefile                            # Developer commands (setup, dev, test, lint, migrate)
├── pyproject.toml                      # uv package dependencies, ruff, mypy, pytest config
├── README.md                           # Architecture documentation & quickstart
└── uv.lock                             # Locked reproducible dependency tree
```

---

### Deep Breakdown of Key Directories

#### `app/core/`
* **Responsibility**: Houses framework infrastructure, security decoders, exception base classes, registry engine, and context handlers.
* **What belongs**: Code that is generic, domain-agnostic, and shared across all future projects (e.g., `registry.py`, `context.py`, `pagination.py`).
* **What does NOT belong**: ORM tables, domain use-cases, business validation rules, or feature endpoints.
* **Why it exists**: Prevents circular dependencies. Modules can import from `core`, but `core` never imports from `modules`.

#### `app/modules/`
* **Responsibility**: Encapsulates all domain-driven business features.
* **What belongs**: Self-contained mini-apps containing their own database models, schemas, services, repositories, and routers.
* **What does NOT belong**: Global middleware registration or framework configuration.
* **Why it exists**: Provides Django-like app encapsulation. Adding a new feature means creating a new directory under `modules/` with zero modifications to global routing files.

#### `app/modules/common/`
* **Responsibility**: Houses cross-cutting domain definitions that multiple modules share.
* **What belongs**: Abstract base models (`TimeStampedBase`), shared Enums (`RoleType`), and validated field types (`EmailField`, `NewPasswordField`).
* **What does NOT belong**: Routers or `apps.py` (it is not a mounted mini-app).

---

## 6. Django-Like Developer Experience in FastAPI

### Achieving Django's Ergonomics without Django's Pitfalls

| Django Feature | Django Approach | Fastango Template Equivalent | Why It's Superior in FastAPI |
| :--- | :--- | :--- | :--- |
| **`startapp` CLI** | `django-admin startapp <name>` | `python scripts/startapp.py <name>` or `make module name=<name>` | Generates typed Pydantic v2 + SQLAlchemy 2.0 async skeletons instantly. |
| **`INSTALLED_APPS`** | Manual list in `settings.py` | Auto-discovery via `app/core/registry.py` with `ENABLED_MODULES` overrides | Zero manual imports needed. Adding a directory auto-registers it; configuration allows selective disabling. |
| **`models.py` & Migrations** | Metaclass discovery in `models.py` | `import_all_models()` scans all modules before Alembic runs | Alembic detects all tables automatically without manual `target_metadata` updates in `env.py`. |
| **`urls.py` Routing** | Nested `urlpatterns` with `include()` | `ModuleConfig` declaring `router` and `public_router` | Mounts routes with versioning and tags automatically while enforcing default-deny auth. |
| **Settings Management** | Global `django.conf.settings` | `pydantic-settings` `BaseSettings` cached singleton | Strongly typed, environment-validated, fail-fast at startup with zero runtime lookup overhead. |
| **`views.py` vs `services.py`**| Views often mix ORM queries with business logic | Strict separation: `router.py` (HTTP/IO) -> `services.py` (Domain Logic/Tx) -> `repositories.py` (SQL) | Clean testability. Services can be unit-tested without HTTP mock harnesses. |

---

## 7. Template vs. Project-Specific Separation

```
┌────────────────────────────────────────────────────────────────────────┐
│                   TEMPLATE VS APPLICATION BOUNDARIES                   │
├───────────────────────────────────┬────────────────────────────────────┤
│ CORE TEMPLATE INFRASTRUCTURE      │ OPTIONAL MODULES (PLUGINS)         │
│ (Ships in base template)          │ (Opt-in blueprints)                │
├───────────────────────────────────┼────────────────────────────────────┤
│ • Settings & Environment Engine   │ • S3 / Cloud Storage Service       │
│ • Database Lifecycle & Guard      │ • Redis Caching & Cache Query      │
│ • Module Auto-Discovery Registry  │ • Background Worker (Arq / Taskiq) │
│ • Enveloped Exception Pipeline    │ • Email / Notification Dispatcher  │
│ • ContextVar Correlation ID       │ • Multi-tenancy Org Middleware     │
│ • Security / JWT Verification     │ • Audit Log Persistence to DB      │
│ • Auth Foundation (UserAuth)      │                                    │
│ • Dual Health Probes (/ready)     │                                    │
│ • Pytest SQLite Async Suite       │                                    │
│ • Scaffolding CLI (startapp.py)   │                                    │
├───────────────────────────────────┴────────────────────────────────────┤
│ PROJECT-SPECIFIC APPLICATION CODE (MUST NEVER POLLUTE TEMPLATE)        │
├────────────────────────────────────────────────────────────────────────┤
│ • Custom business entities (e.g. Products, Orders, Analyses, Reports)  │
│ • Third-party payment gateways (Stripe, PayPal)                        │
│ • ML / ONNX models, weights, tokenizers                                │
│ • Synthetic data generators & seed datasets                            │
│ • Specific domain business rules & score weighting algorithms          │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 8. Dependency & Abstraction Audit

| Abstraction / Pattern | Verdict | Evaluation & Rationale |
| :--- | :--- | :--- |
| **Generic Repository Base Class** (`BaseRepository[T]`) | **REMOVE** | **Anti-Pattern**. Generic repos with methods like `.find_by_filter(**kwargs)` reinvent SQLAlchemy's query API with worse typing and inflexible JOIN capabilities. Use explicit, domain-specific repository methods. |
| **Service Locator via `ContextVar` (`get_db_session()`)** | **SIMPLIFY** | ContextVar is convenient but hides dependencies. In route handlers, inject `db: AsyncSession = Depends(get_db)` and pass it to services, OR retain `db_session_ctx` only for transaction orchestration while providing standard DI for testing. |
| **`@api_response()` Route Decorator** | **SIMPLIFY / REPLACE** | Decorators that strip typing annotations to force envelopes interfere with OpenAPI schema generation. Use native `response_model=APIResponse[SchemaOut]` in route decorators and return domain dicts/models; let centralized exception handlers handle error envelopes. |
| **Empty Pass-Through Repositories** | **REMOVE** | If a service only reads a record by ID, calling `repo.get_by_id` when the repo is literally `select(Model).where(Model.id == id)` in an empty file adds indirection without value. Co-locate simple queries or write real repository methods. |
| **`boto3` in `app/core/storage.py`** | **MAKE OPTIONAL** | `boto3` is synchronous and blocks the asyncio loop. Move S3 storage to an optional recipe using `aioboto3` or standard presigned URL generation, keeping core template dependency-light. |
| **Dual Password Hasher (`passlib` + `bcrypt`)** | **REMOVE passlib** | `passlib` is unmaintained and incompatible with `bcrypt >= 4.1.0`. Use `bcrypt` directly with `anyio.to_thread.run_sync`. |
| **`python-jose` vs `PyJWT`** | **KEEP PyJWT** | `python-jose` has unpatched CVEs. Standardize exclusively on `PyJWT` with explicit algorithm restrictions and claim validation. |

---

## 9. Modern FastAPI & Python Best Practices

### 1. Lifespan Context Manager
Startup and shutdown events (`@app.on_event`) are deprecated. Use the `lifespan` async context manager:
```python
@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("Fastango starting up — environment: %s", settings.APP_ENV)
    for cfg in module_configs:
        await cfg.on_startup()
    yield
    for cfg in reversed(module_configs):
        try:
            await cfg.on_shutdown()
        except Exception:
            logger.exception("Shutdown hook failed for module %s", cfg.name)
    await engine.dispose()  # Close asyncpg connection pool cleanly
    logger.info("Fastango shut down cleanly.")
```

### 2. Modern SQLAlchemy 2.0 Type-Safe Models
Declare ORM models using `Mapped` and `mapped_column` inheriting from `DeclarativeBase`:
```python
from datetime import datetime
import uuid
from sqlalchemy import String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

class Base(DeclarativeBase):
    pass

class TimeStampedBase(Base):
    __abstract__ = True
    created_at: Mapped[datetime] = mapped_column(server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now(), onupdate=func.now(), nullable=False)

class UserAuth(TimeStampedBase):
    __tablename__ = "user_auth"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    user_code: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), default=uuid.uuid4, unique=True, index=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, server_default="true")
```

### 3. Pydantic v2 Schema Normalization
Use `Annotated` with `BeforeValidator` to normalize input edge types once across all schemas:
```python
from typing import Annotated
from pydantic import BaseModel, BeforeValidator, EmailStr, Field

def normalize_email(v: str) -> str:
    return v.strip().lower() if isinstance(v, str) else v

EmailField = Annotated[EmailStr, BeforeValidator(normalize_email)]
PasswordField = Annotated[str, Field(min_length=8, max_length=72)]
```

---

## 10. Production Readiness & Security Review

```
                             INCOMING REQUEST
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    TrustedHostMiddleware     │ <- Blocks Host-header poisoning
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │        CORSMiddleware        │ <- Strict origins, rejects "*" + credentials
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    SecurityHeadersMiddleware │ <- CSP, HSTS, X-Frame, Nosniff
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    RequestIdMiddleware       │ <- Assigns / propagates X-Request-ID
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │    AuditTimingMiddleware     │ <- Process time + client IP logging
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │   Default-Deny Auth Gating   │ <- /private/ requires valid Bearer token
                     └──────────────┬───────────────┘
                                    │
                                    ▼
                     ┌──────────────────────────────┐
                     │       FastAPI Router         │ <- Module Endpoint Execution
                     └──────────────────────────────┘
```

### Critical Security Controls
1. **Secret Key Strength Gate**: In `app/config.py`, throw an error at startup if `APP_ENV != "local"` and `SECRET_KEY` equals the example string or is shorter than 32 characters.
2. **Timing Attack Immunity**: Implement a dummy bcrypt check (`_DUMMY_HASH`) during login when an email does not exist. Both valid and invalid user lookups take ~300ms, eliminating email enumeration side-channels.
3. **Algorithm Locking**: Hardcode `ACCEPTED_ALGORITHMS = ["HS256", "HS384", "HS512"]` inside `decode_token()`. Never read the decode algorithm dynamically from user config to prevent `none` algorithm attacks.
4. **Token Type Segregation**: Tokens carry `"type": "access"` or `"type": "refresh"`. `decode_token(token, expected_type="access")` rejects refresh tokens passed to protected API routes.
5. **Database Resiliency**: Set `pool_recycle=1800` to prevent stale proxy disconnections, `pool_pre_ping=True` to verify socket health, and provide separate `/health` (liveness, no DB hit) and `/health/ready` (readiness, `SELECT 1`) endpoints.

---

## 11. Testing Architecture

### Strategy: Fast In-Memory Unit Tests + Real Token Verification

```
tests/
├── conftest.py               # In-memory SQLite engine, ASGI test client, auth fixtures
├── core/                     # Framework validation
│   ├── test_config.py        # Settings validation & secret key rejection
│   ├── test_middleware.py    # Public vs private route gating & security headers
│   ├── test_registry.py      # Module discovery & disable flags
│   └── test_security.py      # JWT claims, expiration, algorithm locking
└── modules/                  # Feature module tests
    ├── test_auth.py          # Register, login, refresh, constant-time dummy verification
    └── test_users.py         # User CRUD & permissions
```

### Essential Test Fixtures (`tests/conftest.py`)
* **SQLite Foreign Key Enforcement**: SQLite turns off FK checks by default. Attach an event listener:
  ```python
  @event.listens_for(test_engine.sync_engine, "connect")
  def enforce_sqlite_fk(dbapi_connection, _record):
      cursor = dbapi_connection.cursor()
      cursor.execute("PRAGMA foreign_keys=ON")
      cursor.close()
  ```
* **Real Authenticated Test Client**: Tests must mint signed JWTs rather than bypassing authentication:
  ```python
  @pytest_asyncio.fixture
  async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
      app.dependency_overrides[get_db] = lambda: db_session
      token = create_access_token(subject=TEST_USER_CODE, role="user")
      async with AsyncClient(
          transport=ASGITransport(app=app),
          base_url="http://testserver",
          headers={"Authorization": f"Bearer {token}"},
      ) as ac:
          yield ac
      app.dependency_overrides.clear()
  ```

---

## 12. Developer Experience (DX) & Tooling

### The Ideal Onboarding Workflow
```bash
git clone https://github.com/your-org/fastango.git my-backend
cd my-backend
make setup       # Installs uv, creates venv, syncs dependencies, copies .env.example to .env
make migrate     # Runs alembic upgrade head
make dev         # Starts uvicorn with auto-reload on http://localhost:8000
```

### Scaffolding CLI: `startapp`
A custom script (`scripts/startapp.py`) replicates Django's `startapp`:
```bash
python scripts/startapp.py orders
```
Creates `app/modules/orders/` with `apps.py`, `models.py`, `schemas.py`, `repositories.py`, `services.py`, `router.py`, and `constants.py`. On restart, the module is automatically discovered and mounted at `/private/api/v1/orders`.

### Recommended Makefile
```makefile
.PHONY: setup dev test lint format migrate makemigrations module

setup:
	cp -n .env.example .env || true
	uv sync
	uv run pre-commit install

dev:
	uv run uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

test:
	uv run pytest -v --cov=app --cov-report=term-missing

lint:
	uv run ruff check .
	uv run mypy app

format:
	uv run ruff format .
	uv run ruff check --fix .

migrate:
	uv run alembic upgrade head

makemigrations:
	uv run alembic revision --autogenerate -m "$(name)"

module:
	uv run python scripts/startapp.py $(name)
```

---

## 13. Naming Conventions & Project Standards

| Component | Naming Rule | Example | Location |
| :--- | :--- | :--- | :--- |
| **Module Directory** | lowercase, snake_case | `app/modules/user_profiles/` | `app/modules/` |
| **Module Config** | PascalCase ending in `Config` | `UserProfilesConfig(ModuleConfig)` | `apps.py` |
| **ORM Model** | PascalCase, singular noun | `UserAuth`, `Order`, `Project` | `models.py` |
| **Database Table** | lowercase, snake_case, plural | `user_auth`, `orders`, `projects` | `models.py` (`__tablename__`) |
| **Pydantic Schema** | PascalCase with action/role suffix | `UserCreateSchema`, `UserOutSchema` | `schemas.py` |
| **Service Class** | PascalCase ending in `Service` | `UserAuthService`, `OrderService` | `services.py` |
| **Repository Class**| PascalCase ending in `Repository` | `UserAuthRepository`, `OrderRepository` | `repositories.py` |
| **Route Endpoints** | snake_case async functions | `get_current_user()`, `create_order()` | `router.py` |
| **Custom Exceptions**| PascalCase ending in `Exception` | `NotFoundException`, `OrderConflictException` | `core/exceptions.py` or module |
| **Constant Messages**| UPPER_SNAKE_CASE ending in `_MSG` | `USER_CREATED_MSG`, `NOT_FOUND_MSG` | `constants.py` |
| **Pytest Test Files**| snake_case prefixed with `test_` | `test_auth.py`, `test_middleware.py` | `tests/` |

---

## 14. Scalability Stress Test

Let's evaluate this template against an enterprise app containing 12 domains:
*Users, Organizations, Projects, Teams, Billing, Notifications, Audit, Admin, External APIs, Background Jobs, WebSockets, Permissions.*

```
                               ┌──────────────┐
                               │  app/core/   │
                               └──────▲───────┘
                                      │ (shared types & contracts only)
                ┌─────────────────────┼─────────────────────┐
                │                     │                     │
         ┌──────┴──────┐       ┌──────┴──────┐       ┌──────┴──────┐
         │    auth/    │       │    users/   │       │   billing/  │
         └──────▲──────┘       └──────▲──────┘       └──────▲──────┘
                │                     │                     │
                └─────────────────────┼─────────────────────┘
                                      │ (domain service calls)
                               ┌──────┴──────┐
                               │  projects/  │
                               └─────────────┘
```

### Scalability Failure Points & Architectural Solutions

1. **Cross-Module Circular Imports**:
   * *Problem*: `users` module imports `projects.models.Project` for foreign keys, while `projects` imports `users.models.User`.
   * *Solution*: **Loose Foreign Keys by String Name**. SQLAlchemy resolves `ForeignKey("users.id")` lazily by table name. Cross-module business actions must happen through service function calls, never cross-module repository/model mutations.
2. **Cross-Module Transactions**:
   * *Problem*: A billing checkout needs to create an organization, assign a user, and activate a subscription in a single atomic transaction.
   * *Solution*: Pass the active `db: AsyncSession` across service calls. Service methods accept an optional `db: AsyncSession | None = None` and only open `async with db.begin():` if no transaction is already active.
3. **Background Tasks & WebSockets**:
   * *Problem*: Fast HTTP requests must not run long-running tasks.
   * *Solution*: Introduce an optional `app/core/tasks.py` worker interface (backed by Redis / Arq) allowing any service to enqueue asynchronous jobs via `await enqueue_job("send_welcome_email", user_id)`.

---

## 15. Anti-Patterns to Strictly Avoid

1. **Dev-Mode Auth Bypasses**: Never insert `if settings.APP_ENV == "dev": return mock_user` in core security dependencies. Tests and dev tools should mint real signed tokens.
2. **Pass-Through / Forwarding Repositories**: Do not create empty repository methods that simply forward to another module's repository.
3. **Tuples for Error Propagation**: Do not return `(data, error_msg)` from services. Raise typed domain exceptions (`NotFoundException`, `ValidationException`) and let centralized exception handlers build the HTTP response.
4. **Attaching DB Dependency to Root FastAPI App**: Never add `dependencies=[Depends(get_db)]` to `FastAPI()`. Bind it to the API router so `/health` and static assets don't open database connections.
5. **Wildcard CORS with Credentials**: Never allow `CORS_ORIGINS=["*"]` when `allow_credentials=True`. Pydantic validator must reject this at boot.
6. **Synchronous Cryptography on the Event Loop**: Never call `bcrypt.hashpw` or `bcrypt.checkpw` directly inside an async path; always wrap with `anyio.to_thread.run_sync`.
7. **Generic Repositories (`BaseRepository[T]`)**: Avoid over-abstracting database queries into complex generic repositories with dynamic filtering. Write explicit SQLAlchemy 2.0 select queries.

---

## 16. Final Recommended Architecture & Concise Rules

### Architectural Rules
1. **HTTP at the Edge Only**: Routers (`router.py`) handle HTTP request validation, parameter parsing, and calling services. No SQL queries or business logic in routers.
2. **Services Own Business Logic & Transactions**: Services execute domain logic and manage transaction boundaries (`async with db.begin():`). Services raise domain exceptions on failure.
3. **Repositories Own Data Access**: Repositories execute raw SQLAlchemy queries and return ORM models or scalars. Repositories never commit transactions.
4. **Core is Independent**: `app/core/` contains framework infrastructure. `core` must never import from `app/modules/`.
5. **Default-Deny Authentication**: Endpoints declared in `ModuleConfig.router` mount under `/private/api/v1` and require authentication. Only endpoints in `public_router` mount under `/public/api/v1`.
6. **No Pass-Through Wrappers**: If a repository or service method does nothing other than call another single method, eliminate the wrapper.
7. **Consistent Error Enveloping**: All responses and errors (including 400, 401, 403, 404, 409, 422, 429, 500, 503) return `{ "error": bool, "message": str, "data": Any }` with `X-Request-ID`.
8. **Asynchronous CPU Offloading**: CPU-intensive operations (password hashing, heavy encryption) must run in thread pools via `anyio.to_thread.run_sync`.

---

### Incremental Migration Plan (From `fastango_v1` to Target Architecture)

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│     PHASE 1     │     │     PHASE 2     │     │     PHASE 3     │     │     PHASE 4     │
│ Security & Core │ ──> │ Exception Model │ ──> │ Modularity & DX │ ──> │ Tooling & CI/CD │
│   Hardening     │     │   Refactoring   │     │   Cleanups      │     │   Automation    │
└─────────────────┘     └─────────────────┘     └─────────────────┘     └─────────────────┘
```

#### Phase 1: Security & Core Hardening (P0)
* Replace `pyproject.toml` with `uv`-standard dependencies; drop `passlib` and `python-jose`, retain `PyJWT` and `bcrypt`.
* Harden `app/config.py`: add `SECRET_KEY` validator, literal `APP_ENV`, and CORS validation.
* Update `app/core/security.py`: add `anyio.to_thread.run_sync` for bcrypt, `_DUMMY_HASH`, algorithm locking, and remove the dev auth bypass.
* Remove global DB dependency from `app/main.py`.

#### Phase 2: Exception Pipeline & Database Alignment (P0 / P1)
* Upgrade `app/exceptions.py` to handle `FastangoException`, `RequestValidationError`, `RateLimitExceeded`, `IntegrityError`, and `OperationalError`.
* Switch services from tuple returns `(data, err)` to raising domain exceptions (`NotFoundException`, `ValidationException`).
* Update `app/database.py` to use SQLAlchemy 2.0 `class Base(DeclarativeBase)` and add `pool_recycle`.

#### Phase 3: Module Registry & DX Refinements (P1)
* Update `app/core/registry.py` to support dual routing (`router` -> private, `public_router` -> public).
* Add `app/core/context.py` and `app/logging_config.py` for `X-Request-ID` correlation.
* Clean up `app/modules/profile/`: remove empty models and pass-through repositories, rename/merge into `users` module.
* Create `scripts/startapp.py` for automated module scaffolding.

#### Phase 4: Production Tooling & Automation (P1 / P2)
* Create multi-stage `Dockerfile` with non-root user and healthcheck.
* Update `docker-compose.yml` with 127.0.0.1 port bindings and container healthchecks.
* Add `Makefile` and GitHub Actions CI workflow for ruff, mypy, and pytest.

---

## 17. Prioritized Improvement Roadmap

### P0 — Critical (Immediate Fixes Required)
- [x] **Remove Security Bypass**: Delete hardcoded mock identity in `core/security.py`.
- [x] **Wire Complete Exception Handlers**: Envelop `FastangoException`, `RequestValidationError` (422), `RateLimitExceeded` (429), and DB errors.
- [x] **Thread-Offload Bcrypt**: Wrap password hashing and verification in `anyio.to_thread.run_sync`.
- [x] **Harden JWT Decoder**: Enforce required claims (`exp`, `sub`, `type`) and hardcode accepted algorithms.
- [x] **Scrub Settings**: Enforce minimum secret key length and block placeholder secrets in production.

### P1 — High Value (Template Quality & Developer Experience)
- [x] **Migrate to `uv`**: Replace Poetry/requirements.txt with standard `pyproject.toml` and `uv.lock`.
- [x] **Adopt Dual-Mount Registry**: Mount private routes by default and public routes explicitly.
- [x] **Exception-Driven Services**: Eliminate Go-style tuple returns in favor of typed exception raising.
- [x] **Request Correlation ID (`X-Request-ID`)**: Add context variable and logging filter for end-to-end tracing.
- [x] **SQLAlchemy 2.0 Standard**: Migrate `declarative_base()` to `class Base(DeclarativeBase)`.
- [x] **Dual Health Checks**: `/health` (liveness) and `/health/ready` (readiness with DB ping).
- [x] **Scaffolding CLI (`startapp.py`)**: Script to generate new feature modules from templates.

### P2 — Nice to Have (Operational Excellence)
- [ ] **Standardized Pagination**: Generic `PaginatedResponse[T]` helper with page/size query dependency.
- [ ] **Redis Rate-Limiter Backend**: Configure slowapi with Redis backend for multi-worker support.
- [ ] **Multi-stage Dockerfile**: Hardened runtime image with non-root user.
- [ ] **Debug Overlay**: `docker-compose.debug.yml` for remote VS Code / Zed debugging.

### P3 — Optional (Ecosystem Plugins)
- [ ] **Async S3 Storage Module**: `aioboto3` wrapper for cloud file uploads.
- [ ] **Background Task Queue**: Arq / Taskiq async worker integration.
- [ ] **Structured JSON Logger**: JSON format output for Datadog / CloudWatch.

---

## 18. "If This Were My Template" (Senior Architect Verdict)

If I were maintaining this template as the foundational starting point for all my future FastAPI projects over the next 5 years, here is exactly what I would do:

1. **What I would KEEP**:
   * The **auto-discovery module pattern (`app/modules/*/apps.py`)**. It gives the exact organizational satisfaction of Django apps without any framework bloat.
   * The **uncommitted-write guard** in `database.py`. It has saved countless hours of debugging silent transaction rollbacks.
   * The **Pydantic v2 annotated field types** (`EmailField`, `PasswordField`) in `common/schemas.py`.

2. **What I would REMOVE**:
   * **Poetry, passlib, and python-jose**. Replace immediately with `uv`, `bcrypt`, and `PyJWT`.
   * **All Go-style `(data, error)` return tuples**. Python has robust exception handling; raising typed `FastangoException` subclasses makes router code 3x smaller and cleaner.
   * **Empty pass-through repositories and comment-only model files**. Never create a file just to fill an arbitrary checklist.

3. **What I would MERGE & RENAME**:
   * Merge `app/modules/home` and `app/modules/profile` into a clean, canonical **`app/modules/users`** module.
   * Rename `AdminAuth` to **`UserAuth`** (or `User`) in the base template so it serves as a universal user model rather than assuming an admin-only context.

4. **What I would ADD**:
   * **`python scripts/startapp.py <name>`** CLI tool. This is the single biggest DX multiplier for Django developers moving to FastAPI.
   * **Dual `/health` and `/health/ready` endpoints**. Essential for zero-downtime Kubernetes and Docker rollouts.
   * **ContextVar-driven `X-Request-ID`** in all log lines. You cannot debug production without it.
