# Fastango

A Django-inspired modular FastAPI template. Clone it, configure it, migrate,
run, start building features.

Django's organizational win — self-contained apps you drop in a directory —
without Django's machinery. FastAPI stays FastAPI: async, Pydantic-first,
explicit dependency injection.

---

## Quickstart

```bash
git clone <this-repo> my-backend && cd my-backend
make setup      # uv sync, copy local.env.example -> local.env, install hooks
make up         # start postgres + redis
make migrate    # alembic upgrade head
make dev        # http://localhost:8000/docs
uv run python manage.py createsuperuser   # first ADMIN account
```

Then create your first module:

```bash
make module name=orders
```

Restart the server. It is mounted at `/private/api/v1/orders`. There is no
registration step — no `INSTALLED_APPS`, no router imports to edit.

`app/modules/note` is the worked example to copy from: a table, a repository,
paginated list, and create / update / delete scoped to the caller. When you no
longer need it: `rm -r app/modules/note tests/modules/note` and delete its
migration, `alembic/versions/c3a91e7f2b64_note.py`.

---

## The idea in three rules

**1. A feature is a directory.**

```
app/modules/orders/
├── apps.py          # OrdersConfig — name, prefix, tags, routers
├── models.py        # SQLAlchemy tables
├── repositories.py  # queries; never commits
├── schemas.py       # Pydantic in/out
├── services.py      # business logic; owns transactions
├── router.py        # endpoints, one line each
└── constants.py     # module messages
```

Drop it in `app/modules/`, it mounts. Delete the directory, it is gone.

**2. A route's URL states its auth requirement.**

| `apps.py` attribute | Mounts under | Token required |
|---|---|---|
| `router` | `/private/api/v1/...` | yes |
| `public_router` | `/public/api/v1/...` | no |

`router` is the default, so a module that thinks about none of this ships
private. Enforced twice — a default-deny middleware on the `/public/` prefix,
and a guard on the private router itself — so one mounting mistake is not an
opening.

**3. Nobody writes a status code.**

Services raise `NotFoundException`, `ValidationException`, `ForbiddenException`.
Each carries its own status, and one handler maps the whole family. Every
response — success, 404, 422, 429, 503 — comes back in the same envelope:

```json
{ "error": false, "message": "Login successful.", "data": { "...": "..." } }
```

---

## What you get

| | |
|---|---|
| **Reference CRUD** | `app/modules/note` — list / get / create / update / delete with pagination and per-owner scoping. Copy its shape, then delete it |
| **Auth** | register / login / refresh / logout / me, JWT access+refresh with single-use refresh tokens, bcrypt off the event loop, timing-flat login, role guards |
| **Security** | default-deny routing, hardcoded JWT algorithms, required claims, secret-key strength gate, CORS wildcard rejection, CSP/HSTS/COOP/CORP, trusted hosts, Redis-backed proxy-aware rate limiting |
| **Database** | SQLAlchemy 2.0 async, explicit transactions, an uncommitted-write guard that fails loudly instead of losing data, Alembic wired to auto-discovered models |
| **Observability** | `X-Request-ID` on every response and every log line, request timing, liveness + readiness probes, optional Sentry (off unless `SENTRY_DSN` is set) |
| **Testing** | in-memory SQLite with FK enforcement locally, SQLite and Postgres in CI, real signed tokens (no auth bypass, ever), anon/user/admin clients |
| **Tooling** | `uv`, ruff, mypy, pre-commit, a Makefile, 4-job CI including a migration-drift check |
| **Deploy** | multi-stage non-root Docker image, healthcheck, `--proxy-headers` |

---

## Layout

```
app/
├── main.py          # factory, lifespan, health probes
├── config.py        # validated settings
├── database.py      # engine, session, write guard
├── middleware.py    # request-id -> headers -> audit -> auth -> CORS -> host
├── exceptions.py    # every error, one envelope
├── logging_config.py
├── core/            # infrastructure. NEVER imports app.modules.*
└── modules/         # your features
    ├── common/      # only what two or more modules share
    ├── auth/        # register / login / refresh / logout / me
    └── note/        # the reference CRUD module — copy it, then delete it
```

**Where do I put this?** If it is a feature, `app/modules/<feature>/`. If two
modules need it, `app/modules/common/`. If every project needs it, `app/core/`.
If you are unsure, it is a feature.

---

## Commands

`make help` lists them. The full reference with explanations is in
[docs/COMMANDS.md](docs/COMMANDS.md); the architecture and its rules are in
[docs/GUIDE.md](docs/GUIDE.md).

---

## Before you deploy

- `SECRET_KEY` — `openssl rand -hex 32`. The app refuses to start outside
  development with the placeholder or anything under 32 characters.
- `ALLOWED_HOSTS` — your real hostnames.
- `CORS_ORIGINS` — exact origins. `"*"` is rejected at startup because
  credentials are enabled.
- `REDIS_URL` — without it rate limits are per-worker, which means
  `--workers 4` quietly multiplies every limit by four.
- `FORWARDED_ALLOW_IPS` — your proxy's address or CIDR (the image defaults to
  `127.0.0.1`). The image runs `--proxy-headers`, which takes the client address
  from `X-Forwarded-For` only for these hops. Too narrow and every caller shares
  one rate-limit counter; `"*"` lets any client forge the header and bypass it.
- `/docs` is served in development only.
- `SENTRY_DSN` — optional. Empty keeps Sentry off; set it to report errors.
  `SENTRY_TRACES_SAMPLE_RATE` (default `0.1`) controls performance tracing.

## License

MIT.
