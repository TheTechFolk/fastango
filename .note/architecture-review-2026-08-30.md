# FastAPI Template — Architecture Review & Migration Plan

*Date: 2026-08-30*
*Scope: `fastango_v1` (this repo) vs `/home/thededar/Downloads/Summer 2026/argus-backend`*

---

## 1. Executive Summary

**The central finding: these are not two competing architectures. `argus-backend` is `fastango_v1`, forked and hardened by contact with a real application.**

Same `app/core/registry.py`. Same `ModuleConfig`. Same seven-file module skeleton. Same `templates/module/`. Same `{error, message, data}` envelope. Same contextvar session. Same `_has_uncommitted_writes` guard, comment-for-comment.

So the deliverable is not "combine the best of both." It is:

> **Backport argus's `core/` and infrastructure into fastango, delete argus's domain, and add the three things neither project has.**

Argus has independently resolved ~90% of the backlog in `note/review_2026-05-27.md`. Items #1 (exceptions never handled), #3 (dev auth bypass), #5 (dead dependencies), #6 (global DB dependency) — all fixed in argus, and fixed well, with the reasoning written into the comments.

**The architecture is right. Do not redesign it.** Hybrid modular (Option C) is already what both projects are. The gap is not architectural:

| Gap | Where |
|---|---|
| The template is ~6 months behind its own fork | everywhere in `app/core/` |
| The template cannot be cloned and run | no committed `local.env.example`; `.gitignore` excludes `alembic/versions/*.py` |
| Neither project has a task runner | no `Makefile`, no `scripts/` |
| Both have `common/` as an enum dumping ground | `common/enums.py` in both |
| Neither has pagination in the template | argus hand-rolls it per module |

**P0 work is mechanical backporting, not design.**

---

## 2. Current Project Analysis (fastango_v1)

### Architectural philosophy

Explicit and coherent, documented in `Structure_Overview.md`: *"Bring Django's structure to FastAPI, without slowing it down."* A translation of a real Django/DRF project (`core-backend`) — `models.py`/`queries.py`/`services.py`/`views.py`/`urls.py` becomes `models.py`/`repositories.py`/`services.py`/`router.py`/`apps.py`.

The load-bearing idea is **`app/core/registry.py`** — Django's `INSTALLED_APPS` without the list. Drop a directory under `app/modules/`, give it `apps.py` with a `ModuleConfig` subclass, and it mounts. This is the differentiator. Keep it.

### What is good

1. **`registry.py` auto-discovery** (`app/core/registry.py:101`). Zero-registration modules. `import_all_models()` shared between app boot and `alembic/env.py:24` — migrations see exactly what the app sees.
2. **`ENABLED_MODULES` / `DISABLED_MODULES` with models-still-imported semantics** (`registry.py:79-89`). "Disabled != uninstalled" is correct.
3. **The uncommitted-write guard** (`app/database.py:57-102`). Services own transactions via `async with db.begin()`; a request that mutates without one raises instead of silently rolling back a 200. Best code in either repo.
4. **Security-conscious defaults with reasoning in comments**: `SECRET_KEY` with no default (`config.py:24`), JWT `type` claim checked on decode (`security.py:92`), generic non-enumerating auth messages (`auth/constants.py:13,17`), `is_superuser` never read from the request body (`auth/services.py:40`), regression test locking it in (`tests/modules/test_auth.py:38`).
5. **`templates/module/`** as a copy-paste scaffold with a `sed` one-liner. Lazier and more honest than a CLI.
6. **The review note itself** (`note/review_2026-05-27.md`).

### What is unnecessarily complicated

| Thing | Verdict |
|---|---|
| `app/core/audit.py` — `AuditLogService.log_request` | **Dead code.** Never called; `middleware.py:27` logs inline. DB-persist path is a commented stub. Delete. |
| `app/core/storage.py` — `S3StorageService` | Module-level singleton at import; sync `boto3` inside `async def`; silently mocks on `ImportError`. A mock returning a plausible URL when the library is missing is worse than a crash. **Remove from base template.** |
| `app/modules/profile/repositories.py` | Six lines forwarding to `AdminAuthRepository.get_by_admin_code`. Empty layer. |
| `app/modules/home/repositories.py` | Literally `class HomeRepository: pass`. |
| `app/modules/home/models.py`, `profile/models.py` | Comment-only files. Registry already handles a missing `models.py` (`registry.py:73-76`). |
| `app/core/exceptions.py` `http_404()`..`http_409()` | Never imported. Six functions saving four characters. |
| `requirements.txt` **and** a Poetry `pyproject.toml` | They disagree. `pyproject.toml` lists `python-jose`/`passlib` (unused) and **omits `slowapi`**, which `main.py:14` imports at boot — `poetry install` produces a non-importable app. |

### What is missing

- **`local.env.example` is not committed.** `local.env` is on disk, gitignored (`.gitignore:37`), untracked. `Settings` requires `SECRET_KEY` and `DATABASE_URL` with no defaults. **A fresh clone crashes on import with no file to copy from.** Worst bug in the repo for a template.
- **`.gitignore` excludes `alembic/versions/*.py`.** `versions/` holds only `.gitkeep`. A cloned template has zero migrations.
- Exception handlers for `FastangoException`, `RequestValidationError`, `HTTPException`, `IntegrityError`. `app/exceptions.py:22` registers `Exception` only, so **the entire `app/core/exceptions.py` hierarchy is dead** — any `NotFoundException` becomes a 500.
- Request IDs / correlation IDs. Structured logging. `/health/ready`. `engine.dispose()` on shutdown. CI. Task runner. Pagination. `mypy` config (declared as dev dep, never configured). Type checking in pre-commit.
- `refresh`, `logout`, `change-password` — schemas exist (`auth/schemas.py:31,37`), constants exist (`auth/constants.py:6-8`), endpoints do not.

### What is tightly coupled

- **`get_db_session()` is a service locator** (`database.py:40`). Services reach into a contextvar instead of receiving a session. Cost: cannot call a service outside an HTTP request without priming the contextvar. Argus hit this and added a `request_session` fixture (`tests/conftest.py:97`).
- **`inject_db_session_context` is a global app dependency** (`main.py:51`) — `/health` opens a pooled connection per liveness probe. Argus kept this too; both should move it to the API routers.
- **`profile` imports `auth`'s model and repository directly** (`profile/repositories.py:6-7`). Fine at three modules; a dependency graph nobody drew at twelve.
- **`app/core/security.py` defines auth dependencies every module imports** — correct direction (core <- modules).

### What becomes difficult as it grows

1. `common/enums.py` already holds `OrderStatus`, `PaymentStatus`, `PayoutStatus`, `MenuItemStatus`, `ReviewStatus`, `ContentType` — **a food-delivery application's domain enums inside a reusable template**. The dumping ground forming in real time, with three demo modules.
2. `_find_config_class` scans `dir(module)` and returns the first `ModuleConfig` subclass alphabetically. Two configs in one `apps.py`, or an imported one, and the wrong router mounts silently.
3. The `(data, error_msg)` tuple convention (`auth/services.py:25`, `profile/services.py:10`) requires every router to remember the check. Forget once and `None` serializes as the body.
4. Every route repeats `data, msg = await service.x(); return success_response(...)`. At 12 modules, hundreds of lines of identical translation.

---

## 3. argus-backend Analysis

Same skeleton, materially hardened. ~11,500 LOC across 9 modules, 5 committed migrations, ~40 test files, real CI.

### What argus got right that the template lacks

**1. Auth by URL placement — the best idea in either codebase.**

```
ModuleConfig.router        -> /private/api/v1/<prefix>   token required
ModuleConfig.public_router -> /public/api/v1/<prefix>    open
```

Enforced twice, independently: middleware gates on the `/public/` string prefix (`middleware.py:57`), and the private `APIRouter` carries `Depends(get_current_user_code)` (`registry.py:141-144`). A module that thinks about none of this ships private. Version comes *last* in the root so `/public/api/v2` stays public for free (`registry.py:36`).

Converts "did we remember to protect this route?" from a review question into a structural property.

**2. The dev auth bypass is gone.** Fastango's `security.py:111` returns a hardcoded UUID when `APP_ENV in ("local","test","testing")` and no token is sent. Argus deleted it and says why (`middleware.py:83-86`): *"shipped in the production image and was one env var away from disabling auth entirely."* Tests mint real signed tokens (`conftest.py:148`).

**3. Complete exception coverage** (`app/exceptions.py`). Seven handlers, one envelope: `ArgusException` (status read off the class), `RequestValidationError` (field detail in dev only), `RateLimitExceeded`, `IntegrityError`->409, `OperationalError`->503+`Retry-After`, `SQLAlchemyError`, `StarletteHTTPException` (re-attaching headers so 401s keep `WWW-Authenticate`), `Exception`. Adding a new exception type never touches a handler.

**4. `@api_response()`** (`core/decorators.py`). Handlers become one line. The `@wraps` comment is load-bearing — FastAPI resolves signatures through `__wrapped__`, and stripping the return annotation stops FastAPI inferring `response_model` from `-> tuple[dict, str]`.

**5. Config as a security boundary** (`app/config.py`). `APP_ENV` is a `Literal`, not `str` — a typo used to change branch silently. `SECRET_KEY` rejected if placeholder or <32 chars outside dev. `CORS_ORIGINS` rejects `"*"` because credentials are on. `_ENV_FILE` anchored to the package, not CWD. `is_dev`/`is_test` properties so three files stop keeping drifting tuples.

**6. JWT hardening** (`core/security.py:34-41`): `ACCEPTED_ALGORITHMS` hardcoded — *"taking this list from settings meant `JWT_ALGORITHM=none` made the decoder accept unsigned tokens"* — and `REQUIRED_CLAIMS` because PyJWT validates `exp` only when present.

**7. Timing-safe login** (`auth/services.py:80-103`). Unknown email still pays a bcrypt verification against `_DUMMY_HASH`. Without it, ~2ms vs ~300ms is an enumeration oracle regardless of message. bcrypt runs via `anyio.to_thread` (`auth/utils.py:54-61`).

**8. The `alembic check` CI job** (`.github/workflows/ci.yml`, `migrations`). Applies migrations to real Postgres, asks Alembic whether models drifted, tests the down path. The test suite builds its schema with `create_all` and never runs Alembic, so **model drift is structurally invisible to it**. Best single idea in argus's tooling.

**9. `core/security.py` verifies, `auth/utils.py` issues.** Dependency direction stated out loud (`security.py:1-14`): core must not import from a module, or deleting auth stops the whole app booting.

**10. Production Dockerfile.** Multi-stage, `--no-dev`, non-root uid 1001, `HEALTHCHECK`, `--proxy-headers`. Plus the `client_ip()` / rate-limit-key fix (`middleware.py:60`, `rate_limit.py:28`): behind an ingress `request.client.host` is the proxy, which *"collapses the entire internet into one counter, turning a 5/minute login limit into a DoS on your own login endpoint."*

**11. Single dependency source of truth.** `uv` + `pyproject.toml` + `uv.lock`, `[dependency-groups] dev` excluded from the image.

**12. Module `README.md` + `NOTE.md` convention.** README is orientation, NOTE is the long "what will break if you change this" record.

### What is project-specific (do NOT carry over)

`detection/`, `scoring/`, `governance/`, `evaluation/`, `synthetic/`, `analysis/`, `ingestion/`. The ONNX/tokenizers/numpy deps, the model-fetch Dockerfile stage, `ML_DETECTOR_ENABLED`, the `ml` pytest marker, the `RUF001-003` unicode ignores. `common/enums.py`'s `FindingType`/`TargetField`. `common/values.py`'s `quantize_confidence`. `SCORING_FORMULA.md`.

### What argus got wrong

| Issue | Detail |
|---|---|
| `_DUMMY_HASH` at import time | `auth/utils.py:68` runs bcrypt cost-12 (~300ms) at module import — paid by alembic, every CLI invocation, every test collection. Make it lazy. |
| `common/` is a dumping ground *again* | `common/enums.py` holds `FindingType`/`TargetField`. Same disease as fastango's `OrderStatus`. The rule in `common/values.py:3-5` is right; `enums.py` doesn't follow it. |
| No task runner | `GUIDE_COMMAND.md` is 160 lines of commands a human retypes. |
| No pagination helper | `limit`/`offset` `Query(...)` re-declared per route, `RunPage`/`RunResultsPage` per module (`analysis/schemas.py:358,389`). |
| `inject_db_session_context` still global | `main.py:63`. |
| Tests SQLite, prod Postgres | Mitigated by the migrations CI job, not eliminated. `conftest.py:52` hand-enables FK enforcement. |

### Does it provide a Django-like experience? Does it scale?

Yes and yes. Nine modules, one at 2,615 LOC, structure held. Proof: `app/modules/detection/` grew `base.py`, `fusion.py`, `normalize.py`, `runner.py`, `rules.py`, `detectors/`, `configs/` **without splitting the module or touching `core/`**. The seven-file skeleton is a floor, not a ceiling.

Responsibilities are clear: `repositories.py` never commits, `services.py` owns transactions, `router.py` is one line per endpoint, nobody writes a status code.

---

## 4. Side-by-Side Comparison

| Area | fastango_v1 | argus-backend | Best approach |
|---|---|---|---|
| **Project structure** | `app/{main,config,database,middleware,exceptions}.py` + `core/` + `modules/` | Same + `logging_config.py` | **Argus.** Add `logging_config.py`; keep flat root. |
| **Module organization** | 7-file skeleton, auto-discovered | Same + optional `dependencies.py`/`utils.py`/`README.md`/`NOTE.md`/`configs/` | **Argus.** Skeleton is a floor; grow inside the module. |
| **Configuration** | Flat `BaseSettings`, `str` env, no validators | `Literal` env, SECRET_KEY + CORS validators, package-anchored env file, `is_dev`/`is_test` | **Argus, wholesale.** |
| **Database** | `declarative_base()`, unconditional pool args, no dispose | `DeclarativeBase`, sqlite-aware `_engine_options()`, `pool_recycle`, `engine.dispose()` | **Argus.** Both keep the write guard. |
| **API layer** | Single `/api/v1`, auth per-route | `/public/api/v1` vs `/private/api/v1`, default-deny + double guard | **Argus. Headline feature.** |
| **Service layer** | `(data, error_msg)` tuples, router translates | Raise `ArgusException`; return `(data, message)` | **Argus.** Tuples-as-errors is a footgun. |
| **Repository layer** | Static-method classes, never commit | Identical | **Either.** No generic base repository. |
| **Authentication** | Per-route `Depends`, **dev bypass** | Default-deny middleware + router guard, no bypass, `require_role`, timing-safe login, async bcrypt | **Argus.** Bypass is a P0 removal. |
| **Error handling** | 1 handler; custom hierarchy dead | 7 handlers, one envelope, status on the class | **Argus, wholesale.** |
| **Logging** | `basicConfig` at import | `configure_logging()` in lifespan + request-id filter + `X-Request-ID` | **Argus.** |
| **Testing** | 1 client fixture, auth waived by `APP_ENV` | `anon_client`/`client`/`admin_client` with real tokens, `request_session`, SQLite FK pragma | **Argus.** |
| **DI** | `Depends` for auth; contextvar for DB | Identical | **Either.** Keep contextvar. |
| **Scalability** | Untested (3 demo modules) | Proven to 9 modules / 11.5k LOC | **Argus.** |
| **Developer experience** | `templates/module/` + `GUIDE.md`; **clone->crash** | Same + module READMEs + CI; still no task runner | **Neither is finished.** Add a `Makefile`. |
| **Maintainability** | Two disagreeing dep files, no CI, no mypy | One `pyproject.toml` + lock, 4-job CI, ruff (11 rulesets) + mypy | **Argus, wholesale.** |
| **Deployment** | Single-stage root Docker, `version:` compose key | Multi-stage non-root, healthcheck, `--proxy-headers` | **Argus** (minus ML model stage). |

---

## 5. Recommended Architecture

**Hybrid modular — which you already have. Do not change the shape. Sharpen the rules.**

```
app/            framework wiring          (5 files, no business logic)
app/core/       framework-independent     (imports config + stdlib + libs; NEVER a module)
app/modules/    feature slices            (import core and common; not each other)
```

### Why not the alternatives

**Option A (layer-based: `routers/`, `services/`, `models/`)** — Wrong. Adding one feature touches five directories. At twelve features every directory has twelve unrelated files. Deleting a feature means grepping. This is what Django avoided.

**Option B (pure feature-based, flat)** — Wrong for a *template*: the template's value is the infrastructure. If `auth/` and `core/` sit as peers, the boundary between "what I clone" and "what I write" disappears.

**Option C (hybrid)** — Right, and what both projects converged on independently. The `app/` vs `app/core/` vs `app/modules/` split *is* the template/application boundary. A new developer can be told: **"you will only ever create directories under `app/modules/`."** That is the Django feeling.

### Django properties actually being imported

| Django | Fastango equivalent | Verdict |
|---|---|---|
| `INSTALLED_APPS` | `registry.discover_modules()` | better — zero registration |
| `apps.py` / `AppConfig` | `ModuleConfig` | same, plus lifespan hooks |
| `models.py`/`views.py`/`urls.py` | `models.py`/`router.py`/`apps.py` | same muscle memory |
| `settings.py` | `config.py` (pydantic-settings) | better — typed and validated |
| `manage.py` | **`Makefile`** | MISSING — build it |
| `startapp` | `cp -r templates/module` | good enough; do not build a CLI |
| `AbstractBaseModel` | `CommonFieldBase` | same |
| Middleware stack | `configure_middleware()` | same |

**Do not import**: Django's app-loading machinery, a `manage.py` runner, signals, a generic ORM manager layer, an admin site.

---

## 6. Recommended Directory Tree

```
fastango/
├── Makefile                      # NEW. The manage.py replacement.
├── pyproject.toml                # single source of truth (uv + hatchling)
├── uv.lock                       # committed
├── local.env.example             # COMMITTED. Currently missing entirely.
├── docker-compose.yml
├── Dockerfile                    # multi-stage, non-root
├── .pre-commit-config.yaml       # + ruff-format + mypy
├── .github/workflows/ci.yml      # lint | test | migrations | docker
├── README.md                     # what it is, clone->run in 5 lines
├── GUIDE.md                      # architecture + conventions
├── GUIDE_COMMAND.md              # command reference
│
├── app/
│   ├── main.py                   # app factory, lifespan, /health, /health/ready
│   ├── config.py                 # Settings + validators + is_dev/is_test
│   ├── database.py               # engine, session factory, Base, get_db, write guard
│   ├── middleware.py             # request-id -> security headers -> audit -> auth -> CORS -> trusted host
│   ├── exceptions.py             # the 7 handlers
│   ├── logging_config.py         # configure_logging(), RequestIdFilter
│   │
│   ├── core/                     # framework-independent infrastructure
│   │   ├── constants.py          # global fallback messages, token-type claims
│   │   ├── context.py            # request-id contextvar, client_ip
│   │   ├── decorators.py         # @api_response()
│   │   ├── exceptions.py         # AppException family (status on the class)
│   │   ├── pagination.py         # NEW. PageParams dep + Page[T] schema.
│   │   ├── rate_limit.py         # slowapi + redis + proxy-aware key
│   │   ├── registry.py           # ModuleConfig, discover_modules, import_all_models
│   │   ├── responses.py          # APIResponse[T], success_response, error_response
│   │   └── security.py           # decode_token, get_current_user_code, require_role
│   │
│   └── modules/
│       ├── common/               # ONLY what >=2 modules import
│       │   ├── models.py         # TimeStampedBase, CommonFieldBase — base classes only
│       │   ├── schemas.py        # EmailField, NewPasswordField, ExistingPasswordField
│       │   └── enums.py          # RoleType. Nothing else. Ever.
│       │
│       └── auth/                 # the one reference module
│           ├── apps.py  models.py  repositories.py  schemas.py
│           ├── services.py  router.py  constants.py
│           ├── dependencies.py   # registration_enabled
│           ├── utils.py          # hash/sign (core verifies)
│           └── README.md
│
├── alembic/
│   ├── env.py
│   └── versions/                 # COMMITTED. Currently gitignored.
│       └── 0001_auth.py
│
├── templates/module/             # copy-paste scaffold
│
└── tests/
    ├── conftest.py               # anon_client / client / admin_client / db_session / request_session
    ├── test_registry.py
    ├── test_security_controls.py # public/private boundary, JWT, headers, CORS
    └── modules/auth/
```

### Directory responsibilities

| Directory | Responsibility | Belongs | Does NOT belong | Why it exists |
|---|---|---|---|---|
| `app/` (root files) | Wire the framework | App factory, lifespan, middleware stack, handler registration, engine, settings | Any business logic; any domain model | The five files you edit once per project |
| `app/core/` | Framework-independent infrastructure | Things every module imports: envelope, exceptions, decorators, registry, security primitives, pagination | **Anything importing `app.modules.*`** | Enforces the dependency direction the registry rests on |
| `app/modules/common/` | Shared-by-two-or-more only | ORM base classes, shared Annotated field types, `RoleType` | Any enum one module owns. Any domain type. Helpers with one caller | Argus wrote the rule (`common/values.py:3-5`) — now enforce it |
| `app/modules/<feature>/` | One feature, end to end | Everything the feature needs; add files freely as it grows | Another module's internals | A feature is deletable as a directory |
| `alembic/versions/` | Schema history | Every migration, committed | — | Currently broken by `.gitignore` |
| `templates/module/` | The scaffold | Skeleton + README | Working code | Django's `startapp` without a CLI |
| `tests/` | Mirrors `app/modules/` | Fixtures in `conftest.py`; one dir per module | Fixtures duplicated per file | Predictable location |

**Deliberately absent:** `app/api/`, `app/services/`, `app/utils/`, `scripts/`, `app/schemas/`, `app/models/`.

---

## 7. Template vs Application Code

### Core template infrastructure — always present

`config.py` · `database.py` · `logging_config.py` · `middleware.py` · `exceptions.py` · `main.py` · all of `core/` · `common/models.py` · `common/schemas.py` · `common/enums.py` (RoleType only) · `modules/auth/` · `tests/conftest.py` · `templates/module/` · `Makefile` · `Dockerfile` · `docker-compose.yml` · CI · pre-commit · `alembic/`

**`auth/` is infrastructure, not a demo.** Every project needs login. Ship it complete — register, login, refresh, me.

### Optional modules — document, don't ship

Redis cache decorator · background jobs (`arq`/TaskIQ) · S3 storage · email/SMTP · WebSockets · Prometheus metrics · Sentry · feature flags · admin UI · multi-tenancy

**Rule: if fewer than half your next five projects need it, it is a documented recipe in `GUIDE.md`, not code in the template.** By that test, `core/storage.py` and `core/audit.py` both fail today.

### Project-specific — must never enter the template

`home/` · `profile/` · `common/enums.py`'s `OrderStatus`/`PaymentStatus`/`MenuItemStatus`/etc · every argus domain module · ONNX/numpy/tokenizers deps · Dockerfile model stage · `ML_DETECTOR_ENABLED`

**Clean test:** *would this file be in the diff if I cloned for a completely different product?* `profile/` fails. `OrderStatus` fails badly.

---

## 8. Dependency & Abstraction Audit

| Abstraction | Where | Verdict | Reasoning |
|---|---|---|---|
| `ModuleConfig` + `discover_modules` | `core/registry.py` | **Keep** | The whole point. ~140 lines buying zero-registration modules. |
| `_find_config_class` via `dir()` | `registry.py:115` | **Simplify** | Add `and obj.__module__ == module.__name__`. Currently picks first alphabetically. |
| `ENABLED_MODULES`/`DISABLED_MODULES` | `config.py` | **Keep** | ~12 lines, 3 tests, useful per-environment. Cheap. |
| Uncommitted-write guard | `database.py` | **Keep** | Best code in either repo. Silent data loss -> loud failure. |
| `get_db_session()` contextvar | `database.py:61` | **Keep, with eyes open** | It is a service locator. It also removes `db: AsyncSession` from every service signature and keeps handlers one line. Tax is exactly one test fixture (`request_session`). Document it as a deliberate trade. |
| `inject_db_session_context` as **global** dependency | `main.py:63` | **Move** | To the private/public routers. `/health` should not open a connection. |
| `AppException` family, status on class | `core/exceptions.py` (argus) | **Keep** | One handler for N types. Nobody writes a status code. |
| `http_404()`..`http_409()` | fastango `core/exceptions.py:58-75` | **Remove** | Zero callers. |
| `@api_response()` | `core/decorators.py` | **Keep** | Removes ~3 lines from every endpoint. |
| `APIResponse[T]` envelope | `core/responses.py` | **Keep — informed** | Non-standard (not RFC 7807), adds nesting, forces `response_model=APIResponse[T]`. But uniform, matches DRF heritage, every handler already covers it. Switching costs more than it saves. |
| `AuditLogService` | `core/audit.py` | **Remove** | Dead. Middleware already logs. |
| `S3StorageService` | `core/storage.py` | **Move to optional** | Sync boto3 in `async def`; import-time singleton; silently mocks. |
| `ProfileRepository` | `profile/repositories.py` | **Remove** (with `profile/`) | Pure pass-through. |
| `HomeRepository: pass` | `home/repositories.py` | **Remove** | Placeholder for a layer with no work. |
| `(data, error)` returns | fastango services | **Replace** | Raise `AppException`; return `(data, message)`. |
| Static-method repository classes | both | **Keep** | A namespace, not a hierarchy. Correct. |
| **Generic `BaseRepository[T]`** | *neither has one* | **Never add** | Most common over-abstraction in FastAPI boilerplates. `select(Model).where(...)` is already the generic API. |
| `common/enums.py` as global enum home | **both** | **Move** | Domain enums go in their owning module. |
| `_DUMMY_HASH` at import | argus `auth/utils.py:68` | **Simplify** | 300ms bcrypt on every import. Make it lazy. |
| `configure_middleware`/`configure_exceptions` | both | **Keep** | Keeps `main.py` at 90 lines. |
| Per-module `constants.py` + global fallbacks | argus | **Keep** | Two tiers, no string written twice. |
| `require_role()` factory | argus `security.py:110` | **Keep** | Closure returning a dependency — idiomatic FastAPI. |

**Circular-dependency risks: one real, one latent.** `rate_limit.py:32` imports `middleware` inside a function to break a cycle — resolves by moving `client_ip()` into `core/context.py`. And `core/security.py:26` imports `app.modules.common.enums` — core reaching into modules, the one direction the registry forbids. Move `RoleType` to `core/constants.py`.

---

## 9. FastAPI Best Practices Review

| Practice | Status | Action |
|---|---|---|
| Lifespan (not `@on_event`) | OK both | — |
| `engine.dispose()` on shutdown | argus only | Backport (P0) |
| Shutdown hook isolated in try/except | argus only | Backport |
| `APIRouter` nesting | OK both | Adopt public/private roots |
| Pydantic v2 | OK both | argus uses PEP 695 `class APIResponse[T]` — cleaner |
| `pydantic-settings` + validators | argus only | Backport (P0) |
| Async/sync boundary | BAD fastango (sync bcrypt on loop, sync boto3) | Backport `anyio.to_thread` |
| SQLAlchemy 2.x `DeclarativeBase` | fastango uses legacy `declarative_base()` | Backport |
| Alembic + `import_all_models()` | OK both | Add `alembic check` to CI |
| Explicit transaction boundaries | OK both | Keep as-is |
| HTTP client management | neither | Add lifespan-managed `httpx.AsyncClient` only per project |
| Background tasks | neither | Leave out; document `arq` |
| Middleware ordering | argus (documented innermost-first) | Backport |
| Exception handlers | BAD fastango | Backport (P0) |
| OpenAPI in prod | BAD fastango publishes docs anonymously | Backport `if settings.is_dev` |
| API versioning | — | Use argus's version-last roots |
| Pagination | MISSING both | **Build `core/pagination.py`** |
| Ruff | fastango: `E,F,W,I,N,UP` | Backport argus's `+B,ASYNC,SIM,C4,RUF,S` |
| Mypy | fastango: dep declared, never configured | Backport argus's `[tool.mypy]` |
| pytest-asyncio | fastango has deprecated `event_loop` fixture | Delete it (`asyncio_mode="auto"` already set) |
| Env config | BAD fastango: relative `env_file`, no `.example` | Backport `_ENV_FILE` + commit example (P0) |

**Libraries NOT to add**, despite popularity: `SQLModel` (couples table and wire schema), `dependency-injector` (`Depends` is enough), `structlog` (the `RequestIdFilter` already solves correlation), `celery` (sync-first, heavyweight), `fastapi-users` (opinionated to the point of fighting you — your `auth/` is 520 lines you fully control), `orjson` (measure first).

**Worth it:** `uv`, `slowapi`, `anyio`.

---

## 10. Production Readiness

### Security

| Control | fastango | argus | Action |
|---|---|---|---|
| Secret handling | no `.example`, weak key accepted | placeholder + length validator | **P0 backport** |
| Auth bypass | **`APP_ENV`-gated bypass in prod code** | removed | **P0 remove** |
| Default-deny routing | opt-in per route | private by placement | **P0 backport** |
| Password hashing | implicit cost, blocks loop | explicit rounds, threaded | Backport |
| Account enumeration | message-safe, timing-unsafe | both | Backport |
| JWT algorithms | from settings (`alg:none` risk) | hardcoded allowlist | **P0 backport** |
| Required JWT claims | none | present | Backport |
| Token type confusion | OK both | OK | — |
| Privilege escalation via body | OK both, tested | OK | — |
| CORS | no wildcard guard | validator | Backport |
| Trusted hosts | `testserver` in prod default | test-env only | Backport |
| Rate limiting | in-memory, proxy-blind | Redis, proxy-aware | Backport |
| Security headers | 4 headers | + CSP, COOP, CORP | Backport |
| Error leakage | `str(exc)` in local/test | same, env is a `Literal` | Backport |
| Docs exposure | public in prod | dev only | **P0 backport** |
| Dep vulnerabilities | dead `python-jose`/`passlib` | removed | Backport |
| Authorization (roles) | none | `require_role()` | Backport |
| Token revocation | none | none | **Optional** — document a Redis `jti` denylist |

### Reliability

Transactions OK both. Pool management OK argus (`pool_recycle`, `pre_ping`, dialect-aware). Graceful shutdown OK argus (`engine.dispose()` in lifespan). Startup failure OK both. Health checks OK argus (liveness/readiness split — a liveness probe that fails on a DB outage gets the container *killed instead of drained*).

Missing in both, correctly so for a template: retries, circuit breakers, request timeouts. The one worth adding: `--timeout-keep-alive` and a body-size cap.

### Observability

Request IDs: argus. Structured logging: formatted, not JSON — fine until you have an aggregator. Metrics: neither — optional. Error tracking: neither — optional (Sentry is 3 lines). Audit logging: both log HTTP requests; neither persists a domain audit trail. **Correct call — DB audit logging is per-project.** Delete fastango's stub.

### Deployment

Argus wins everything: multi-stage, non-root, `--no-dev`, HEALTHCHECK, `--proxy-headers`, 4-job CI. Backport all minus the model stage. Fix `docker-compose.yml`'s obsolete `version: "3.9"` key.

---

## 11. Testing Architecture

**Keep argus's shape.** Not `unit/ integration/ api/` — that split forces you to categorize a test before writing it, and the honest answer is usually "both." Mirror the source:

```
tests/
├── conftest.py                    # every shared fixture
├── test_registry.py               # module discovery, enable/disable, module deps
├── test_security_controls.py      # public/private boundary, JWT, headers, CORS
└── modules/
    └── auth/
        ├── test_auth_api.py       # through the HTTP client
        └── test_auth_service.py   # direct, via request_session
```

**Fixtures to ship** (all in argus's `conftest.py`):

| Fixture | Purpose |
|---|---|
| `setup_database` (autouse) | create_all / drop_all per test |
| `db_session` | isolated session + uncommitted-write guard |
| `request_session` | primes the contextvar so services can be called directly |
| `anon_client` | no token — the fixture that proves 401s happen |
| `client` | authenticated as USER with a **real signed token** |
| `admin_client` | same, as ADMIN |
| `auth_header()` | helper for ad-hoc identities |

**Auth testing: mint real tokens.** Never waive auth by environment. That was fastango's bypass, it shipped to production, and it is the single most important lesson argus learned.

**Test database:** in-memory SQLite for speed + the `alembic check` CI job against real Postgres. SQLite alone gives false greens on UUID/JSONB/`func.now()`; testcontainers everywhere costs 30s per run. Keep argus's `PRAGMA foreign_keys=ON` (`conftest.py:52`) — without it your FKs are decorative.

**Mocking:** almost none. Real DB, real tokens, real middleware. Mock only network I/O at the boundary.

**Factories:** skip `factory_boy`. Plain helper functions in `conftest.py`.

**Coverage:** argus's `[tool.coverage]` config is right. Floor at 70%, don't gate on it — gate on the migrations job, which catches a class of bug coverage never will.

---

## 12. Developer Experience

**Target:**

```bash
git clone <template> my-project && cd my-project
make setup       # uv sync, cp local.env.example -> local.env, pre-commit install
make up          # docker compose up -d postgres redis
make migrate     # alembic upgrade head
make dev         # uvicorn --reload
```

**The `Makefile` is the highest-value missing artifact in both repos.** It replaces `GUIDE_COMMAND.md`'s 160 lines of retyping and *is* your `manage.py`:

```makefile
setup:    ; uv sync && cp -n local.env.example local.env && uv run pre-commit install
dev:      ; uv run uvicorn app.main:app --reload
test:     ; uv run pytest -q
lint:     ; uv run ruff check . && uv run ruff format --check . && uv run mypy app
fix:      ; uv run ruff check --fix . && uv run ruff format .
migrate:  ; uv run alembic upgrade head
revision: ; uv run alembic revision --autogenerate -m "$(m)"
check:    ; uv run alembic check
up:       ; docker compose up -d postgres redis
module:   ; cp -r templates/module app/modules/$(name) && \
            grep -rl "sample\|Sample" app/modules/$(name) | \
            xargs sed -i 's/sample/$(name)/g; s/Sample/$(shell python -c "print('$(name)'.title())")/g' && \
            rm app/modules/$(name)/README.md
```

`make module name=orders` gives you `startapp` in nine lines of Make. **Do not build a Python CLI for this** — a CLI is a package, an entry point, tests, and a release process, to replace `cp -r`.

Everything else: commit `local.env.example` (P0). Add `mypy` and `ruff-format` to `.pre-commit-config.yaml`. Keep `GUIDE.md`/`GUIDE_COMMAND.md`. Adopt argus's module-level `README.md`/`NOTE.md`. Rewrite root `README.md` so the first screen is clone->run.

---

## 13. Naming & Conventions

| Kind | Convention | Example |
|---|---|---|
| Modules | lowercase singular noun | `auth/`, `billing/`, `notification/` |
| Files | fixed names, plural for collections | `models.py`, `repositories.py`, `services.py`, `schemas.py`, `constants.py`, `router.py`, `apps.py`, `dependencies.py`, `utils.py` |
| Models | singular PascalCase; `__tablename__` singular snake | `Auth` -> `"auth"`, `Organization` -> `"organization"` |
| Public identifier | `code: Mapped[uuid.UUID]`, never expose the PK | `Auth.code` |
| Repositories | `<Model>Repository`, static methods, never commit | `AuthRepository.get_by_email` |
| Repo methods | `get_by_*` (-> `| None`), `list_*`, `create`, `update`, `delete` | — |
| Services | `<UseCase>Service`, instance per request, own transactions | `AuthService`, `TokenRefreshService` |
| Service returns | `(data, message)` on success; **raise** on failure | — |
| Schemas | `<Name>Schema` input, `<Name>Response`/`<Name>OutSchema` output | `LoginSchema` -> `TokenResponse` |
| Routers | `router` (private), `public_router` (public). No prefix/tags in the file | — |
| Handlers | verb or noun matching the route; one line | `async def login(...)` |
| Config class | `<Module>Config(ModuleConfig)` | `AuthConfig` |
| Dependencies | verb phrase reading as a condition | `registration_enabled`, `require_role` |
| Exceptions | `<Reason>Exception`, subclass `AppException`, status on the class | `NotFoundException` |
| Constants | `SCREAMING_SNAKE`, messages end `_MSG` | `INVALID_CREDENTIALS_MSG` |
| Tests | `tests/modules/<module>/test_<area>.py`; names state the guarantee | `test_refresh_token_rejected_as_access_token` |
| Settings | `SCREAMING_SNAKE`, grouped by comment banner | `JWT_ACCESS_TOKEN_EXPIRE_MINUTES` |

**Import order** (ruff `I` enforces): stdlib -> third-party -> `app.config` -> `app.core.*` -> `app.database` -> `app.modules.*`. Absolute imports only; no relative imports. Both projects already do this — a reason argus stayed navigable at 11.5k lines.

---

## 14. Scalability Test — 12 modules

Modules: `auth`, `users`, `organizations`, `projects`, `teams`, `billing`, `notifications`, `audit`, `admin`, `integrations`, `jobs`, `realtime`.

**What holds:** the registry (a `pkgutil` walk — 12 is the same as 3). `import_all_models()`. Route mounting. The public/private split. Exception handlers. The Makefile. `@api_response()`. Test layout.

**Where complexity appears:**

1. **`common/` becomes the dumping ground.** Not a prediction — already happened in *both* codebases. `OrderStatus`/`MenuItemStatus` in fastango, `FindingType`/`TargetField` in argus. *Fix now:* `common/` holds base classes, shared Annotated types, and `RoleType`. Nothing else.

2. **Cross-module coupling.** `billing` needs `Organization`. `notifications` needs `User`. `audit` needs everything. Argus hit this and documented the exact failure (`common/values.py:6-12`): detection imported scoring for one helper, inverting pipeline order. The rule that works:

   > **Leaf modules import only `core/` and `common/`. Orchestrator modules may import leaves.** State each module's tier in its `apps.py` docstring.

   Argus's `analysis/` legitimately imports `detection`, `scoring`, `governance` — it *is* the pipeline. What isn't fine is `detection` importing `scoring`.

3. **Import cycles.** Two smells exist today at 3 and 9 modules: `rate_limit.py:32`'s function-scoped import of `middleware`, and `core/security.py:26` importing `app.modules.common.enums`. Both fix cleanly. At twelve, add one test walking `app.modules.*` imports asserting the tier rule — cheaper than `import-linter`.

4. **`app/main.py` and `middleware.py` stay small.** `main.py` is 93 lines at 9 modules. Scales because modules configure themselves.

5. **Modules outgrow seven files.** Already proven fine: `detection/` has 15 files plus `detectors/` and `configs/`; `analysis/run_services.py` is 643 lines. **The skeleton is a floor.** Splitting a module because a file got long is the wrong move.

6. **Background jobs and WebSockets don't fit the registry.** `ModuleConfig` mounts routers. A `jobs` module needs a worker entrypoint importing `app.modules.*` without FastAPI. *Don't pre-build.* When needed: a `discover_tasks()` sibling to `import_all_models()` plus `worker.py`. Ten lines, written the day it matters.

7. **Migrations.** At twelve modules `alembic check` in CI becomes load-bearing.

8. **Enum churn.** Argus's `FindingType` docstring is the model: mark shared enums **FROZEN**, document what each value migration cost. Adopt for any enum written to a column.

**Verdict: the architecture scales to twelve modules with two rule changes** — the `common/` discipline and the module-tier rule. Neither requires restructuring.

---

## 15. Anti-Patterns — do not carry forward

| # | Anti-pattern | Where | Why |
|---|---|---|---|
| 1 | **Auth bypass gated on an env var** | fastango `core/security.py:111` | Ships in the production image. One `APP_ENV=local` in staging and every route is public. |
| 2 | **Uniform layers regardless of need** | `home/repositories.py` (`pass`), `home/models.py`, `profile/models.py` (comments), `profile/repositories.py` (pass-through) | Files existing so the directory looks symmetrical. |
| 3 | **`common/` as a domain-enum dump** | both `common/enums.py` | A food-delivery `OrderStatus` in a reusable template. |
| 4 | **Two disagreeing dependency files** | fastango `pyproject.toml` + `requirements.txt` | `poetry install` yields a non-importable app — `slowapi` imported at boot, absent from `pyproject.toml`. |
| 5 | **Dead exception hierarchy** | fastango `core/exceptions.py` vs `app/exceptions.py:22` | Six exception classes nothing handles. Every one becomes a 500. |
| 6 | **`(data, error)` tuples as the error channel** | fastango services | Go-style in a language with exceptions. One forgotten check returns `None` as the body. |
| 7 | **Silent mocking on ImportError** | `core/storage.py:37` | Returns a plausible S3 URL when boto3 is missing. Fails in prod, looks fine in dev. |
| 8 | **Dead stub with a real class name** | `core/audit.py` | Looks like audit logging exists. It does not. |
| 9 | **Docs published anonymously in production** | fastango `main.py:47-49` | A free map of the attack surface. |
| 10 | **Uncommitted migrations** | fastango `.gitignore` | A template that cannot build its own schema. |
| 11 | **No committed `.env.example`** | fastango | Clone -> import -> `ValidationError`. Nothing to copy. |
| 12 | **Env-file path relative to CWD** | fastango `config.py:11` | Running uvicorn from anywhere but the repo root silently skips it. |
| 13 | **Accepted JWT algorithms from settings** | fastango `security.py:82` | `JWT_ALGORITHM=none` makes the decoder accept unsigned tokens. |
| 14 | **`basicConfig` at import** | fastango `main.py:24` | Hands root-logger INFO to Alembic, pytest, every importer; fights uvicorn. |
| 15 | **Expensive work at import time** | argus `auth/utils.py:68` | 300ms bcrypt on every import, including Alembic and test collection. |
| 16 | **`testserver` in the production allowed-hosts default** | fastango `config.py:27` | TrustedHost accepts it from anyone. |
| 17 | **Global DB dependency on every route** | both, `main.py` | `/health` opens a pooled connection per probe. |
| 18 | **Generic `BaseRepository[T]`** | *neither — keep it that way* | SQLAlchemy is already the generic layer. |

---

## 16. Final Recommendations

### A. Recommended architecture

**Hybrid modular, three tiers, one dependency direction.**

```
app/         framework wiring          — edited once per project
  core/      framework infrastructure  — imports config + libs, NEVER a module
  modules/   feature slices            — imports core + common, not each other
```

Auth decided by **route placement** (`/public/api/v1` vs `/private/api/v1`), enforced twice. Modules self-register via `apps.py`. Services own transactions and raise typed exceptions. Routers are one line. `core/` never imports a module.

### B. Directory tree

See §6.

### C. Architectural rules

1. **Routers handle HTTP only.** One line per endpoint: call a service, return `(data, message)`. Never a status code, never a query, never business logic.
2. **Services own business logic and transactions.** `async with db.begin():` for writes. Raise `AppException` subclasses to fail.
3. **Repositories own queries and never commit.** Static methods on a per-aggregate class. No generic base.
4. **Nobody writes a status code outside `core/exceptions.py`.** The exception class carries it.
5. **`core/` never imports `app.modules.*`.** Core verifies credentials; the auth module issues them.
6. **Leaf modules never import each other.** Only orchestrator modules may import leaves, and they say so in their `apps.py` docstring.
7. **`common/` holds only what two or more modules import.** Base classes, shared field types, `RoleType`. A domain enum lives with its owner.
8. **A route is private unless a `public_router` deliberately mounts it.**
9. **Every response uses the same envelope** — success and every error.
10. **Every module is deletable.** `rm -rf app/modules/<name>` plus a migration must leave the app booting.
11. **The seven-file skeleton is a floor, not a ceiling.** Add files inside a module; don't split it.
12. **No environment relaxes a security control.** Environment gates docs, error verbosity, and HSTS. Never authentication.

### D. Template principles

- **If it isn't in four of your next five projects, it's a documented recipe, not code.**
- **Prefer one obvious way over one configurable way.**
- **Abstractions need two callers before they exist.**
- **Every non-obvious decision carries its reason in a comment.** Argus's comments are the best documentation in either repo.
- **The template must run in five commands from a clean clone**, and CI must prove it.
- **Delete before you add.**

### E. What NOT to add

Generic `BaseRepository[T]` · a `startapp` CLI (Make covers it) · `SQLModel` · a DI container · GraphQL · an admin UI · multi-tenancy scaffolding · WebSockets · Celery · a plugin system · CQRS/event sourcing · a permission framework beyond `require_role` · an ORM abstraction over SQLAlchemy · `utils/` · a `common/` "helpers" module · S3/email/SMS clients in the base · in-template Prometheus/Sentry · an `AuditLog` table.

Each is a real decision the *application* should make. A template that pre-decides them is a framework.

### F. Migration plan — incremental, always-green

**Phase 0 — Unbreak the clone (1/2 day, P0).** Bugs, not refactors.
1. `git add -f local.env.example` (sanitized, placeholder SECRET_KEY) — currently there is *no* env template committed.
2. Remove `alembic/versions/*.py` from `.gitignore`; generate and commit the initial migration.
3. Delete `requirements.txt`; move to `uv` + `pyproject.toml` + committed `uv.lock`, with argus's `[dependency-groups] dev`. Drop `python-jose`/`passlib`; add `slowapi`, `redis`, `greenlet`.
4. Add the `Makefile`.
5. Add argus's CI verbatim, minus the `docker` model steps.

*Ship it. The template is now clonable.*

**Phase 1 — Backport `core/` (1-2 days, P0).** Mechanical; argus's files drop in with a rename.
6. `app/config.py` <- argus (Literal env, validators, `_ENV_FILE`, `is_dev`/`is_test`).
7. `app/core/constants.py`, `core/context.py`, `app/logging_config.py` <- argus (new files).
8. `app/core/exceptions.py` + `app/exceptions.py` <- argus (the 7 handlers). Delete `http_4xx()` helpers.
9. `app/core/decorators.py` <- argus (`@api_response()`).
10. `app/core/security.py` <- argus. **Delete the dev bypass.** Move `RoleType` into `core/constants.py` so core stops importing a module.
11. `app/database.py` <- argus (`DeclarativeBase`, `_engine_options()`, `pool_recycle`). Keep the write guard.
12. `app/main.py` <- argus (`configure_logging()` in lifespan, `engine.dispose()`, docs gated on `is_dev`, `/health/ready`).

**Phase 2 — The routing change (1 day, P0).** The one breaking change; do it alone.
13. `core/registry.py` <- argus: `PRIVATE_ROOT`/`PUBLIC_ROOT`, `public_router`, double guard. Fix `_find_config_class` with `obj.__module__ == module.__name__`.
14. `app/middleware.py` <- argus: default-deny auth, request-id, `client_ip()`, CSP/COOP/CORP. Move `client_ip` to `core/context.py` to kill the `rate_limit`->`middleware` cycle.
15. `core/rate_limit.py` <- argus (Redis + proxy-aware key).
16. Move `inject_db_session_context` off the app onto the two routers.

**Phase 3 — Auth as the reference module (1 day, P1).**
17. Replace `app/modules/auth/` with argus's: `Auth` model, `utils.py`, `dependencies.py`, `refresh` + `/me`, timing-safe login, threaded bcrypt. **Make `_DUMMY_HASH` lazy.**
18. Rewrite `tests/conftest.py` <- argus (`anon_client`/`client`/`admin_client`, real tokens, `request_session`, FK pragma).
19. Port `tests/test_security_controls.py`.

**Phase 4 — Delete (1/2 day, P1).**
20. `rm -rf app/modules/home app/modules/profile` — demo code.
21. `rm app/core/audit.py app/core/storage.py` — dead and optional.
22. Strip `common/enums.py` to `RoleType`. Add `common/schemas.py` <- argus's field types.
23. Delete the deprecated `event_loop` fixture.

**Phase 5 — Fill the shared gaps (1 day, P1/P2).**
24. **Write `core/pagination.py`** — the one piece neither project has. `PageParams` dependency + `Page[T]` schema, ~30 lines.
25. Update `templates/module/` <- argus's better-documented version.
26. `Dockerfile` <- argus (multi-stage, non-root), minus the model stage. Drop the `version:` key from compose.
27. Ruff `select` <- argus's; add `[tool.mypy]`; add `mypy` + `ruff-format` to pre-commit.
28. Rewrite `README.md` around clone->run. Adopt the module `README.md` convention.

Each phase leaves a green suite. Phase 2 is the only one that changes URLs.

### G. Prioritized roadmap

**P0 — Critical**
1. Commit `local.env.example` — clone currently crashes
2. Un-ignore and commit `alembic/versions/*.py`
3. Delete the `APP_ENV` auth bypass
4. Backport the 7 exception handlers (the hierarchy is dead code)
5. Hardcode `ACCEPTED_ALGORITHMS`; add `REQUIRED_CLAIMS`
6. Single dependency source (`uv` + `pyproject.toml` + lock); drop `python-jose`/`passlib`, add `slowapi`
7. Backport hardened `config.py` (SECRET_KEY + CORS validators, `Literal` env, anchored env file)
8. Gate `/docs` on `is_dev`
9. Adopt public/private route roots + default-deny middleware
10. Add the `Makefile`
11. Add CI, including the `alembic check` job

**P1 — High value**
12. Request IDs + `configure_logging()` in lifespan
13. `engine.dispose()` + isolated shutdown hooks
14. Redis-backed, proxy-aware rate limiting
15. Threaded bcrypt + explicit rounds + timing-safe login
16. Replace `(data, error)` tuples with raise + `@api_response()`
17. Complete auth: `refresh`, `/me`, `require_role`
18. Backport `conftest.py` (real tokens, three clients)
19. `DeclarativeBase`, `pool_recycle`, sqlite-aware engine options
20. Delete `home/`, `profile/`, `audit.py`, `storage.py`
21. Strip `common/enums.py`; add `common/schemas.py`
22. Multi-stage non-root Dockerfile
23. `/health` + `/health/ready`

**P2 — Nice to have**
24. `core/pagination.py`
25. Full security headers (CSP/COOP/CORP)
26. Fix `_find_config_class` module check
27. Move `inject_db_session_context` to the routers
28. Ruff ruleset expansion + mypy config
29. Module `README.md` convention + updated `templates/module/`
30. Move `client_ip` to `core/context.py` (kills the import cycle)
31. Make `_DUMMY_HASH` lazy
32. Rewrite root `README.md`

**P3 — Optional / documented recipes only**
33. Redis `jti` denylist for revocation
34. JSON structured logging
35. Prometheus metrics
36. `arq`/TaskIQ background jobs
37. Redis cache decorator
38. Sentry
39. Testcontainers Postgres
40. S3 storage as an optional module

---

## 17. "If This Were My Template"

**Fastango is six months behind its own fork. Stop treating this as a comparison and start treating it as a backport.** Argus is what your template becomes after a real application argues with it for a summer. That argument is expensive and you already paid for it — the comments in argus's `middleware.py`, `config.py`, and `rate_limit.py` are the receipts. Collect them.

**Keep, and never let anyone talk you out of:** the module registry. The uncommitted-write guard — best thing in either repo, turns silent data loss into a loud crash. The `/public` vs `/private` route roots — auth becomes a structural property of a URL rather than a review checklist item. `templates/module/` as a `cp -r`. The habit of writing *why* in the comment.

**Remove without ceremony:** `home/`, `profile/`, `audit.py`, `storage.py`, `http_4xx()`, `requirements.txt`, the `event_loop` fixture, the auth bypass, and every domain enum in `common/`. ~600 lines. The template gets better at exactly the rate it gets smaller. `profile/repositories.py` — six lines forwarding to another module's repository — is the clearest illustration of the disease: a layer that exists because the skeleton has a slot for it.

**Merge:** the two exception modules into one family with status on the class. The two dependency files into `pyproject.toml`. The three drifting environment tuples into `is_dev`/`is_test`. `GUIDE_COMMAND.md`'s 160 lines into a `Makefile`.

**Rename:** `AdminAuth` -> `Auth` ("admin" was leaking from a previous project). `admin_code` -> `code`. `AdminAuthService` -> `AuthService`.

**Restructure:** only the routing roots. Nothing else about the shape needs to change. The temptation with a review this long is to conclude the architecture is wrong. It isn't. `app/` + `core/` + `modules/` is correct, it is Django's organizational win without Django's machinery, and argus proved it holds at 11.5k lines across nine modules without `core/` growing a single file.

**Add, in this order:** the `Makefile`, `local.env.example`, committed migrations, CI with the `alembic check` job, `core/pagination.py`.

**Three things to say out loud to whoever maintains this next:**

1. **The template's job is to be deletable-from, not extended-into.** Every file you ship is a file five future projects must read and decide about. `core/storage.py` is 118 lines making one project's life 5% easier and four projects' lives slightly worse. Ship `auth/` complete because everyone needs login. Ship nothing else optional.

2. **`alembic check` in CI is worth more than fifty tests.** The suite builds its schema with `create_all` and never runs Alembic, so model drift is *structurally invisible* to it. The highest-leverage twelve lines of YAML in either repo.

3. **Never let an environment variable relax authentication.** You wrote that bypass, argus deleted it, and the deletion comment explains that it shipped in the production image. Make it a written template principle, because the next person to add a convenience under `if settings.is_dev` will have a very good reason.

**On the two decisions you'll be tempted to revisit:** the response envelope is non-standard and I would still keep it — uniform, every handler already covers it, and RFC 7807 buys nothing your clients are asking for. And the contextvar session *is* a service locator, a real cost, paid in exactly one test fixture; in exchange every service signature loses its `db` parameter and every handler stays one line. Keep it, but write down that it was a trade, so nobody later "fixes" it without knowing what it bought.

**What I would not build:** a `fastango` CLI. `note/review_2026-05-27.md` ranks it the #1 Django-parity win; that is the one recommendation in it I think is wrong. `make module name=orders` is nine lines of Make against a package with an entry point, tests, versioning, and a release process. `cp -r templates/module` is already lazier and more honest — the scaffold is readable, editable, and needs no maintenance. Spend that week on the migration plan.

**Time to a template worth starting five projects from: about five days**, four of them typing argus's files into fastango with a rename. The design work is done. It's in `/home/thededar/Downloads/Summer 2026/argus-backend`.
