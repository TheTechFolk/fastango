# Fastango — Architecture Plan (canonical)

*Updated: 2026-08-30 — post-implementation*
*Status: **implemented and verified**. Commits `763d467` (phases 0–5), `a612d92` (docs reorg).*
*Supersedes `architecture-review-2026-08-30.md` and `gemini_architecture_plan.md`, both kept as provenance.*

---

## 0. Where this stands

`argus-backend` was `fastango_v1`, forked and hardened by contact with a real
application. The work was never a redesign — it was a backport plus four things
neither project had. **All six phases are done, on branch
`feat/architecture-plan`, verified against real Postgres, Redis and Docker.**

| | |
|---|---|
| Tests | 56 passing |
| Lint / types | ruff + ruff-format + mypy clean |
| Migrations | `upgrade` → `check` → `downgrade` round-trip on Postgres 16 |
| Image | 305 MB, non-root uid 1001, dev deps absent |
| Modules shipped | `auth` (reference), `common` (base classes only) |
| Remaining | three small items in §6 |

---

## 1. What was built

### Phase 0 — unbreak the clone
- `local.env.example` **committed**. A fresh clone previously crashed on import:
  `SECRET_KEY` and `DATABASE_URL` have no defaults and there was no file to copy.
- `alembic/versions/*.py` **un-ignored**, initial migration committed. The
  template could not previously build its own schema.
- Single dependency source: `uv` + `pyproject.toml` + `uv.lock`.
  Dropped `requirements.txt`, `python-jose`, `passlib` (unused; unpatched CVEs).
  Added `slowapi`, `redis`, `greenlet` — `slowapi` is imported at boot and was
  missing from the Poetry block, so `poetry install` produced a non-importable app.
- `Makefile` + 4-job CI (lint | test | migrations | docker).

### Phase 1 — core
- `config.py`: `Literal` `APP_ENV`, SECRET_KEY placeholder/length gate, CORS
  wildcard rejection, package-anchored env file, `is_dev`/`is_test`.
- New: `core/constants.py`, `core/context.py`, `logging_config.py`.
- Seven exception handlers, status carried on the class. The `AppException`
  hierarchy was previously dead code behind a bare `Exception` handler.
- `core/security.py`: hardcoded `ACCEPTED_ALGORITHMS` (`JWT_ALGORITHM=none` was
  accepted before), `REQUIRED_CLAIMS`, `require_role`. **Dev auth bypass deleted.**
- `database.py`: `DeclarativeBase`, SQLite-aware engine options, `pool_recycle`.
- `main.py`: logging in lifespan, `engine.dispose()`, isolated shutdown hooks,
  docs gated on `is_dev`, `/health` + `/health/ready`.

### Phase 2 — routing
- Dual-mount registry: `router` → `/private/api/v1`, `public_router` →
  `/public/api/v1`. Default-deny, enforced twice.
- `_find_config_class` now checks `__module__`; it previously took whatever
  sorted first in `dir()`.
- Default-deny auth middleware, request-id, CSP/COOP/CORP.
- Rate limiter: Redis storage + proxy-aware key. `get_remote_address` collapsed
  every caller into one bucket behind an ingress.
- DB session binds to the routers, not the app, so `/health` opens no connection.

### Phase 3 — auth
- `Auth` model (table `auth`, public `code`), `refresh` + `/me`, timing-flat
  login against a lazily-computed dummy hash, bcrypt via `anyio.to_thread`.
- `conftest.py`: real signed tokens, `anon_client`/`client`/`admin_client`,
  `request_session`, SQLite FK pragma.

### Phase 4 — deletions
`home/`, `profile/` (pass-through repos, comment-only models), `core/audit.py`
(never called), `core/storage.py` (sync boto3, silent mock on ImportError),
`common/enums.py` (a food-delivery app's enums in a reusable template).

### Phase 5 — the gaps
`core/pagination.py`, updated module scaffold, multi-stage non-root Dockerfile,
ruff + mypy config, rewritten README / GUIDE / GUIDE_COMMAND.

### Post-implementation — docs reorg (`a612d92`)
`.note/` untracked and gitignored (scratch, not part of what someone clones);
`Structure_Overview.md` moved to `docs/` with its relative link repointed.

---

## 2. Verification record

Everything below was executed, not assumed.

| Claim | How it was checked |
|---|---|
| A fresh clone runs | Extracted **git-tracked files only** into a temp dir, copied `local.env.example`, imported the app. Boots, 7 routes mount. |
| Migrations match the models | Real Postgres 16 container: `upgrade head` → `check` ("No new upgrade operations detected") → `downgrade base` → clean. With `compare_type` and `compare_server_default` on. |
| The schema is right on Postgres | `code` is native `uuid`, timestamps are `timestamptz` defaulting to `now()`, `is_active` is a real `boolean`, unique btree indexes on `code` and `email`. |
| The app works on Postgres, not just SQLite | Live server: readiness through asyncpg, register, `/me` with UUID round-trip, login, duplicate register hitting a **real** unique constraint → 400 via the `IntegrityError` handler. |
| The image is production-shaped | Builds; runs as `uid=1001(app)`; `pytest`/`ruff`/`mypy`/`pre_commit` absent; `fastapi`/`slowapi`/`jwt`/`bcrypt`/`redis`/`asyncpg` present; Docker HEALTHCHECK reports `healthy`. |
| Rate limiting actually works | Redis-backed: 5 logins allowed, 6th → 429, `retry-after: 60`, in the app's envelope. Counter present in Redis under a **per-IP** key, confirming the proxy-aware `key_func`. |
| Security properties are real | Live: private route without token → 401 enveloped; refresh token on `/me` → "Invalid token type."; duplicate register → non-enumerating 400; wrong-password and unknown-email responses byte-identical; email normalized on input; HSTS correctly absent in dev. |
| `make module` works | `make module name=orders` scaffolds, renames `sample`→`orders` / `Sample`→`Orders`, and auto-mounts at `/private/api/v1/orders` — **private by default**. |

---

## 3. The architecture

### Shape

```
app/         framework wiring          — edited once per project
  core/      framework infrastructure  — imports config + libs, NEVER a module
  modules/   feature slices            — imports core + common, not each other
```

Hybrid modular. Not layer-based (adding one feature touches five directories);
not flat feature-based (the template/application line disappears). This split
*is* that line: **you will only ever create directories under `app/modules/`.**

### Tree as built

```
fastango/
├── Makefile                      # the manage.py replacement
├── pyproject.toml / uv.lock      # one dependency source
├── local.env.example             # committed
├── Dockerfile                    # multi-stage, non-root
├── docker-compose.yml            # loopback-bound postgres + redis
├── .pre-commit-config.yaml       # ruff, ruff-format, mypy, check-yaml
├── .github/workflows/ci.yml      # lint | test | migrations | docker
├── README.md  GUIDE.md  GUIDE_COMMAND.md
├── docs/Structure_Overview.md    # historical origin study
│
├── app/
│   ├── main.py  config.py  database.py
│   ├── middleware.py  exceptions.py  logging_config.py
│   ├── core/
│   │   ├── constants.py    # messages, token-type claims, RoleType
│   │   ├── context.py      # request-id contextvar + client_ip
│   │   ├── decorators.py   # @api_response()
│   │   ├── exceptions.py   # AppException family
│   │   ├── pagination.py   # PageParams + Page[T]
│   │   ├── rate_limit.py  registry.py  responses.py  security.py
│   └── modules/
│       ├── common/         # models.py (base classes), schemas.py (field types)
│       └── auth/           # apps models repositories schemas services router
│                           # constants dependencies utils README
├── alembic/versions/       # committed
├── templates/module/       # copy-paste scaffold
└── tests/
    ├── conftest.py
    ├── core/               # test_config, test_middleware, test_registry, test_security
    └── modules/auth/       # test_auth_api, test_auth_service
```

### Rules

1. Routers handle HTTP only. One line per endpoint.
2. Services own business logic and transactions. **Raise** to fail; never return
   an error tuple. Never an optional `db` parameter.
3. Repositories own queries and never commit.
4. Nobody writes a status code outside `core/exceptions.py`.
5. `core/` never imports `app.modules.*`.
6. Leaf modules never import each other. **Cross-module foreign keys use the
   string table name** — `ForeignKey("auth.id")` — never a model import.
7. `common/` holds only what two or more modules import.
8. A route is private unless a `public_router` deliberately mounts it.
9. Every response uses the same envelope and carries `X-Request-ID`.
10. Every module is deletable.
11. The seven-file skeleton is a floor, not a ceiling.
12. No environment relaxes a security control. Environment gates docs, error
    verbosity and HSTS. **Never authentication.**
13. CPU-bound work goes to a thread.

### Middleware order (outermost first)

`TrustedHost → CORS → SecurityHeaders → RequestId → AuditTiming → Auth → router`

CORS sits outside auth so a 401 keeps its CORS headers.

---

## 4. Decisions on record

### Settled during planning

| Question | Decision | Why |
|---|---|---|
| Keep `@api_response()`? | **Keep** | It strips only the *return* annotation so FastAPI stops inferring `response_model` from `-> tuple`. Removing it means writing `success_response(...)` in every handler — the boilerplate it exists to delete. |
| Keep the contextvar session? | **Keep, documented** | A service locator, and a deliberate trade: no `db` in any service signature, one-line handlers. Cost is exactly one fixture (`request_session`). |
| `startapp.py` or `make module`? | **`make module`** | Nine lines of Make vs a script needing a `scripts/` dir that then attracts more scripts. Verified working. |
| Docker files in `docker/`? | **Root** | A subdir breaks `docker compose up` from the root and changes the build context. |
| A second `users/` module? | **No** | A `UserProfile` table's columns are 100% project-specific. |
| Table naming | **Singular** | Matches the `auth` table that already existed. |
| `core/storage.py` | **Removed** | Sync boto3 in `async def`, import-time singleton, silent mock on ImportError. |

### Changed during implementation

- **`RoleType` moved to `core/constants.py`.** `core/security.py` reads the role
  on every request; importing it from `app.modules.common` inverted the one
  dependency direction the registry rests on.
- **`client_ip` moved to `core/context.py`.** It killed the real import cycle
  where `rate_limit` imported `middleware` inside a function to break the loop.
- **`alembic/script.py.mako` modernized** so future revisions are lint-clean
  instead of permanently ignoring `UP`/`I` on generated files.
- **`templates/` excluded from ruff** — the scaffold imports
  `app.modules.sample`, which does not exist, so every import-sorting verdict on
  it is wrong by construction.
- **`GUIDE.md` and `GUIDE_COMMAND.md` rewritten** beyond the planned scope. Both
  described Poetry and the old single `/api/v1` root; leaving actively-wrong
  docs is worse than the gap.
- **One commit, not six.** The plan said Phase 2 should be isolated. The phases
  are interdependent — Phase 1's core does not import without Phase 2's registry
  — so splitting retroactively would have produced commits that individually
  fail. One honest commit instead of a fabricated history.

### Audit corrections (2026-08-30)

A repo-wide over-engineering audit ran after implementation. **Its central
finding was a category error, and that error is the most valuable thing to come
out of it** — see §5.

| Audit said | Verdict | Evidence |
|---|---|---|
| Delete `NotFoundException` / `AlreadyExistsException` | **Rejected** | 4 references across `README.md`, `GUIDE.md`, `templates/module/README.md` as *the* example of the error model. It is the product, not dead code. |
| Delete `require_role` / `get_current_user_role` | **Rejected** | `RoleType` is signed into every token and stored on every row. Without these the role claim is decorative. Fix is to *document* it, not delete it. |
| Delete `admin_client` fixture | **Rejected** | The fixture for role-gated routes; falls with `require_role`. |
| Delete `templates/module/models.py` + `repositories.py` | **Rejected** | A scaffold's job is commented examples you uncomment. The anti-pattern is comment-only files in *real* modules. |
| Delete `.dockerignore` `!README.md` | **Rejected — the audit was wrong and so was I** | Proven by test: `pyproject.toml` declares `readme = "README.md"`, and building without it fails with `OSError: Readme file does not exist`. It is inert *only* because the builder uses `--no-install-project`. For defensive config, inert is the success condition. |
| Move `httpx` to dev group | **Accepted, applied** | Both `app/` hits are comments; no import. 56 tests pass, app boots, absent from the image. |
| Drop `python-multipart` | **Accepted, applied** | No `Form`/`File`/`UploadFile` anywhere; tests pass without it. Failure mode if wrong is loud and clear. |
| Delete planning docs / `Structure_Overview.md` | **Superseded** | Solved better by ignoring `.note/` and moving the doc to `docs/` (`a612d92`). |
| `pagination.py` is speculation | **Conceded, kept** | Genuinely built because the plan said "neither project has it" — a reason to note a gap, not fill it. Kept because a template that makes you hand-roll `limit`/`offset` on your first list endpoint has a real hole, and `templates/module/README.md` documents it as the convention. |

Net honest yield of the audit against code: **one dependency move.**

---

## 5. Template principles

- **In a template, "zero callers" is the expected state for an extension point.**
  Dead-code heuristics that work on applications produce false positives here.
  The test is not *"does anything call it"* but *"would the first project that
  needs it have to write it from scratch?"* `NotFoundException` with no raisers
  is not dead — it is the API.
- **Inert defensive config is succeeding, not failing.** A guard that never
  fires is doing its job. Do not delete it for being quiet.
- **If it isn't in four of your next five projects, it's a recipe, not code.**
- **Abstractions need two callers before they exist** — except extension points,
  per the first rule. Know which one you are looking at.
- **Prefer one obvious way over one configurable way.**
- **Every non-obvious decision carries its reason in a comment.**
- **The template must run in five commands from a clean clone**, and CI must
  prove it.
- **The template's job is to be deletable-from, not extended-into.**
- **Delete before you add.**

### Three things for whoever maintains this next

1. **`alembic check` in CI is worth more than fifty tests.** The suite builds
   its schema with `create_all` and never runs Alembic, so model drift is
   structurally invisible to it.
2. **Never let an environment variable relax authentication.** The bypass this
   template used to have shipped in a production image.
3. **Two decisions were deliberate trades**, both documented in `GUIDE.md` §5:
   the non-standard response envelope, and the contextvar session. Do not let
   either be "fixed" by someone who does not know what it bought.

---

## 6. Open items

| | Item | Status |
|---|---|---|
| 1 | `httpx` → `[dependency-groups] dev` | **Done** (`1a4c0b1`). Verified absent from the image. |
| 2 | Drop `python-multipart` | **Done** (`1a4c0b1`). Re-add with the first upload endpoint; FastAPI's error names it. |
| 3 | `note/review_2026-05-27.md` (no dot) still tracked | Every substantive item in it is now done. Move to `docs/`, ignore, or delete — it is in git history either way. |
| 4 | Wire `require_role` into `templates/module/README.md` | The audit found it because nothing points at it. Discoverability fix, not a deletion. |
| 5 | Branch not merged | `feat/architecture-plan` is 2 commits ahead of `main`, unpushed. |

---

## 7. What NOT to add

Generic `BaseRepository[T]` · a `startapp` CLI · `SQLModel` · a DI container ·
GraphQL · an admin UI · multi-tenancy scaffolding · WebSockets · Celery · a
plugin system · CQRS/event sourcing · a permission framework beyond
`require_role` · an ORM abstraction over SQLAlchemy · `utils/` · a `common/`
"helpers" module · S3/email/SMS clients in the base · in-template
Prometheus/Sentry · an `AuditLog` table.

Each is a real decision the *application* should make. A template that
pre-decides them is a framework, which is not what this is.

---

## 8. Anti-patterns, permanently out

Auth bypasses gated on an env var · layers created to satisfy a skeleton ·
`common/` as a domain-enum dump · two disagreeing dependency files · exception
hierarchies nothing handles · `(data, error)` tuples as the error channel ·
silent mocking on ImportError · dead stubs with real class names · docs
published anonymously in production · uncommitted migrations · no committed env
template · env-file paths relative to the CWD · accepted JWT algorithms read
from settings · `logging.basicConfig` at import · expensive work at import time ·
`testserver` in a production allowed-hosts default · a DB dependency on the root
`FastAPI()` · generic `BaseRepository[T]` · optional `db` on service methods ·
cross-module model imports for foreign keys.
