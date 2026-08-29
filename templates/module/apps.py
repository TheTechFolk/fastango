# app/modules/sample/apps.py
from app.core.registry import ModuleConfig
from app.modules.sample.router import router


class SampleConfig(ModuleConfig):
    name = "sample"
    prefix = "/sample"
    tags = ["Sample"]

    # Mounted at /private/api/v1/sample — every route needs a valid access
    # token, enforced by the auth middleware. This is the default on purpose:
    # a module that thinks about none of this ships private.
    router = router

    # Mounted at /public/api/v1/sample — reachable with no token. Opt in only
    # for what genuinely must work unauthenticated (login, webhooks), and give
    # those their own APIRouter in router.py.
    # public_router = public_router

    # Guards applied to every route in this module, e.g.:
    # from fastapi import Depends
    # from app.core.constants import RoleType
    # from app.core.security import require_role
    # dependencies = [Depends(require_role(RoleType.ADMIN))]

    # async def on_startup(self) -> None:
    #     """Runs once when the application starts."""

    # async def on_shutdown(self) -> None:
    #     """Runs once when the application shuts down."""
