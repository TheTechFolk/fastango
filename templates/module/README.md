# Module Template

Skeleton for a new Fastango module. No CLI needed.

## Usage

```bash
make module name=orders
```

That copies this directory to `app/modules/orders`, renames the `sample`/`Sample`
placeholders, and removes this README. Restart the server — the module is
auto-discovered and mounted at `/private/api/v1/orders`. There is no
registration step.

## Public vs private

A route's auth requirement is decided by **where it mounts**, not by a list
somewhere:

| `apps.py` attribute | Mounts under | Token required |
|---|---|---|
| `router` | `/private/api/v1/orders` | yes |
| `public_router` | `/public/api/v1/orders` | no |

`router` is the default, so a new module is private until someone deliberately
adds a `public_router`. The auth middleware gates on the `/public/` prefix alone
— nothing else needs updating when you add a module.

## Files

| File | Responsibility |
|---|---|
| `apps.py` | ModuleConfig — name, prefix, tags, routers, optional module-wide dependencies |
| `models.py` | SQLAlchemy ORM tables (delete if the module owns none) |
| `repositories.py` | Async DB read/write operations — never commits |
| `schemas.py` | Pydantic request/response shapes; reuse the field types in `app/modules/common/schemas.py` |
| `services.py` | Business logic and transactions. Return `(data, message)`; raise an `AppException` to fail |
| `router.py` | FastAPI endpoints — no prefix/tags here (owned by `apps.py`) |
| `constants.py` | Module messages; global fallbacks live in `app/core/constants.py` |
| `dependencies.py` | Route guards, if the module has any (optional) |

This is a **floor, not a ceiling**. A module that grows an engine, a rules file
or a `detectors/` package adds files inside itself — it does not get split.

## Conventions worth knowing

- **Never write a status code.** Each `AppException` subclass in
  `app/core/exceptions.py` carries its own (`NotFoundException` → 404,
  `ValidationException` → 400), and one handler maps the whole family.
- **`@api_response()` builds the envelope.** Handlers return `(data, message)`
  and stay one line. Skip it on endpoints returning a `Response` subclass.
- **Writes own their transaction** — `async with db.begin():`. `get_db()` does
  not auto-commit, and uncommitted writes raise at request end.
- **Leaf modules do not import each other.** Cross-module foreign keys use the
  string table name.
- **Pagination is `Depends(page_params)` + `Page[T]`** from `app/core/pagination.py`.
