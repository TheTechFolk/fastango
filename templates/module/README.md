# Module Template

Skeleton for a new Fastango module. No CLI needed — copy, rename, done.

## Usage

```bash
# 1. Copy the template (replace "orders" with your module name)
cp -r templates/module app/modules/orders

# 2. Rename the sample/Sample placeholders
grep -rl "sample\|Sample" app/modules/orders | xargs sed -i 's/sample/orders/g; s/Sample/Orders/g'

# 3. Remove this README from the copy
rm app/modules/orders/README.md
```

Restart the server — the module is auto-discovered and mounted at
`/api/v1/orders`. No registration step.

## Files

| File | Responsibility |
|---|---|
| `apps.py` | ModuleConfig — name, prefix, tags, optional module-wide dependencies |
| `models.py` | SQLAlchemy ORM tables (delete if the module owns no tables) |
| `repositories.py` | Async DB read/write operations |
| `schemas.py` | Pydantic request/response shapes |
| `services.py` | Business logic and transactions |
| `router.py` | FastAPI endpoints — no prefix/tags here (owned by `apps.py`) |
| `constants.py` | User-facing messages and module constants |
