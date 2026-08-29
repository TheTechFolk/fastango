# Fastango — Architecture Guide

The reasoning behind the structure, and the rules that keep it working as the
application grows. [README.md](../README.md) is the quickstart;
[COMMANDS.md](COMMANDS.md) is the command reference.

---

## 1. Why hybrid modular

Three tiers, one dependency direction:

```
app/         framework wiring          — edited once per project
  core/      framework infrastructure  — imports config + libs, NEVER a module
  modules/   feature slices            — imports core + common, not each other
```

**Not layer-based** (`routers/`, `services/`, `models/`): adding one feature
touches five directories, and at twelve features every directory holds twelve
unrelated files. Deleting a feature becomes a grep.

**Not flat feature-based**: the template's value is the infrastructure. If
`auth/` and `core/` are peers, the line between "what I cloned" and "what I
wrote" disappears.

**Hybrid** keeps that line exactly where it belongs. You will only ever create
directories under `app/modules/`.

---

## 2. Request lifecycle

Middlewares are registered innermost-first; the last `add_middleware` call is
the outermost wrapper.

```
        request
           │
    TrustedHost          Host-header poisoning
           │
    CORS                 strict origins; "*" + credentials rejected at boot
           │
    SecurityHeaders      CSP, HSTS, COOP, CORP, nosniff, frame-deny
           │
    RequestId            assigns / propagates X-Request-ID
           │
    AuditTiming          duration, client ip, user, status
           │
    Auth                 default-deny: /private/** needs a valid Bearer token
           │
    Router               private root re-checks auth; both roots bind the DB session
           │
    Route -> Service -> Repository
```

CORS sits *outside* auth deliberately: a 401 that loses its CORS headers is a
network error in the browser instead of a 401.

---

## 3. The layers

### `router.py` — HTTP only

```python
@router.get("/{code}", response_model=APIResponse[OrderOutSchema])
@api_response()
async def get_order(code: uuid.UUID):
    """One order."""
    return await OrderService(code).get()
```

One line. No SQL, no business rules, no status codes. `@api_response()` turns
the `(data, message)` a service returns into the envelope.

Do **not** decorate endpoints returning a `Response` subclass (`FileResponse`,
`StreamingResponse`) — their body is already final.

### `services.py` — business logic and transactions

```python
class OrderService:
    async def create(self, data: OrderCreateSchema) -> tuple[dict, str]:
        db = get_db_session()
        async with db.begin():                       # writes own their boundary
            if await OrderRepository.get_by_ref(db, data.ref):
                raise ValidationException(ORDER_EXISTS_MSG)
            order = await OrderRepository.create(db, Order(**data.model_dump()))
        return {"code": order.code}, ORDER_CREATED_MSG
```

Return `(data, message)` on success. **Raise** to fail — never return an error
tuple. `get_db()` does not auto-commit, and a request that ends with pending
writes raises rather than silently discarding them.

### `repositories.py` — queries, and never a commit

Static methods on a class-as-namespace. No inheritance, no generics, and
**no `BaseRepository[T]`** — SQLAlchemy's `select()` is already the generic
query API, and wrapping it produces worse typing and worse joins.

### `models.py` — tables

Inherit `CommonFieldBase` for `created_at` / `updated_at` / `is_active`. Expose
a `code: uuid.UUID` and never the sequential primary key.

Cross-module foreign keys use the **string table name**:

```python
owner_id: Mapped[int] = mapped_column(ForeignKey("auth.id", ondelete="CASCADE"))
```

SQLAlchemy resolves it lazily, so `orders` never imports `auth`'s model class
and the two stay independently deletable.

---

## 4. Errors

Every failure is an exception carrying its own status:

| Raise | Status |
|---|---|
| `ValidationException` | 400 |
| `UnauthorizedException` | 401 |
| `ForbiddenException` | 403 |
| `NotFoundException` | 404 |
| `AlreadyExistsException` | 409 |

`app/exceptions.py` also envelopes `RequestValidationError` (422),
`RateLimitExceeded` (429), `IntegrityError` (409), `OperationalError` (503),
any other `SQLAlchemyError`, framework `HTTPException`s, and the catch-all.
Adding a new exception type never requires touching a handler.

Exception detail reaches the client in development only. Every error response
carries `X-Request-ID`, which is also on every log line — that is how a user's
bug report gets matched to a stack trace.

> **Do not use `AlreadyExistsException` for registration.** A 409 confirms the
> email is taken, which is exactly what the generic message exists to hide.

---

## 5. Two deliberate trades

Both look like mistakes if you do not know what they bought. Do not "fix"
either without reading this.

**The response envelope is non-standard.** It is not RFC 7807 and it adds a
level of nesting. It is also uniform across every status, already handled
everywhere, and matches the DRF idiom this template descends from. Keeping it
costs less than migrating away from it.

**`get_db_session()` is a service locator.** Services read the session from a
`ContextVar` instead of receiving it. That hides a dependency — and it keeps
`db` out of every service signature and every handler one line. The entire cost
is one test fixture (`request_session`), which primes the ContextVar so a
service can be called without an HTTP request in flight.

If you ever replace it, replace it with an **explicit `db` parameter
everywhere**. Never with an optional `db: AsyncSession | None = None` that
opens a transaction only when one is not already active — that is a nested-
transaction bug, and the write guard exists because of it.

---

## 6. Rules

1. Routers handle HTTP only.
2. Services own business logic and transactions. Raise to fail.
3. Repositories own queries and never commit.
4. Nobody writes a status code outside `core/exceptions.py`.
5. `core/` never imports `app.modules.*`.
6. Leaf modules never import each other. Cross-module FKs use string table names.
7. `common/` holds only what two or more modules import.
8. A route is private unless a `public_router` deliberately mounts it.
9. Every response uses the same envelope and carries `X-Request-ID`.
10. Every module is deletable.
11. The seven-file skeleton is a floor, not a ceiling — grow files *inside* a module.
12. No environment relaxes a security control. Environment gates docs, error
    verbosity and HSTS. Never authentication.
13. CPU-bound work goes to a thread (`anyio.to_thread.run_sync`).

---

## 7. Conventions

| Kind | Rule | Example |
|---|---|---|
| Module directory | lowercase, singular | `auth/`, `billing/` |
| ORM model | singular PascalCase | `Auth`, `Organization` |
| Table name | **singular** snake_case | `auth`, `organization` |
| Public identifier | `code: Mapped[uuid.UUID]` | never expose the PK |
| Repository | `<Model>Repository`, static methods | `AuthRepository.get_by_email` |
| Repo methods | `get_by_*`, `list_*`, `create`, `update`, `delete` | |
| Service | `<UseCase>Service`, one per request | `AuthService` |
| Service return | `(data, message)`; raise to fail | |
| Schema | `<Name>Schema` in, `<Name>OutSchema` out | `LoginSchema` |
| Routers | `router` (private), `public_router` | no prefix/tags in the file |
| Module config | `<Module>Config(ModuleConfig)` | `AuthConfig` |
| Exception | `<Reason>Exception` | `NotFoundException` |
| Constant | `SCREAMING_SNAKE`, messages end `_MSG` | `INVALID_CREDENTIALS_MSG` |
| Test | name states the guarantee | `test_refresh_token_rejected_as_access_token` |

Import order (ruff enforces): stdlib → third-party → `app.config` →
`app.core.*` → `app.database` → `app.modules.*`. Absolute imports only.

---

## 8. Testing

```
tests/
├── conftest.py       # db_session, request_session, anon/client/admin_client
├── core/             # config, middleware, registry, security
└── modules/<name>/   # test_<name>_api.py, test_<name>_service.py
```

- **Auth in tests is real.** Fixtures mint signed tokens. There is no
  environment that waives authentication, and there never will be — the bypass
  this replaces shipped in a production image.
- In-memory SQLite with `PRAGMA foreign_keys=ON`, because SQLite leaves FK
  enforcement off and a suite that never checks them proves nothing.
- Almost no mocking: real DB, real tokens, real middleware.
- SQLite is not Postgres. The CI `migrations` job closes that gap by applying
  migrations to real Postgres and running `alembic check`.

---

## 9. Optional recipes

Deliberately **not** in the template — if fewer than half your projects need
it, it is a recipe, not code.

| Want | Do |
|---|---|
| Background jobs | `arq` or TaskIQ against the Redis already in compose. Add a `worker.py` and a `discover_tasks()` beside `import_all_models()`. |
| Caching | `redis.asyncio` client in lifespan; a decorator on repository methods. |
| S3 / file storage | `aioboto3`, or presigned URLs so bytes never touch the API. Not `boto3` — it is sync and blocks the loop. |
| Email | An optional module with a lifespan-managed client. |
| Token revocation | A Redis `jti` denylist checked in `decode_token`. |
| JSON logs | Swap the formatter in `logging_config.py`. |
| Metrics | `prometheus-fastapi-instrumentator`, mounted in `main.py`. |
| Error tracking | `sentry-sdk` init in lifespan. |

---

## 10. Scaling past ten modules

What holds: the registry, model discovery, route mounting, the public/private
split, the handlers, the Makefile, the test layout.

What needs discipline:

1. **`common/` is the dumping ground.** It always is. Base classes and shared
   field types only — a domain enum lives with its owner.
2. **Module tiers.** Leaf modules import `core` and `common`. An orchestrator
   module may import leaves, and says so in its `apps.py` docstring. A leaf
   importing a leaf inverts your pipeline order.
3. **`alembic check` in CI stops being nice and becomes load-bearing.** The test
   suite builds its schema with `create_all` and never runs Alembic, so model
   drift is structurally invisible to it.
4. **Freeze enums written to columns.** Document what each value change costs.
5. **Modules outgrowing seven files is fine.** Add files inside. Never split.
