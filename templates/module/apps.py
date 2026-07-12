# app/modules/sample/apps.py
from app.core.registry import ModuleConfig
from app.modules.sample.router import router


class SampleConfig(ModuleConfig):
    name = "sample"
    router = router
    prefix = "/sample"
    tags = ["Sample"]
    # Guards applied to every route in this module, e.g.:
    # from fastapi import Depends
    # from app.core.security import get_current_user_code
    # dependencies = [Depends(get_current_user_code)]

    # async def on_startup(self) -> None:
    #     """Runs once when the application starts."""

    # async def on_shutdown(self) -> None:
    #     """Runs once when the application shuts down."""
