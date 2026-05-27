# app/modules/auth/apps.py
from app.core.registry import ModuleConfig
from app.modules.auth.router import router


class AuthConfig(ModuleConfig):
    name = "auth"
    router = router
    prefix = "/auth"
    tags = ["Auth"]
