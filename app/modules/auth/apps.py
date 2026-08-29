# app/modules/auth/apps.py
from app.core.registry import ModuleConfig
from app.modules.auth.router import private_router, public_router


class AuthConfig(ModuleConfig):
    name = "auth"
    prefix = "/auth"
    tags = ["Auth"]

    # /public/api/v1/auth/{register,login,refresh} — no token, by definition.
    public_router = public_router
    # /private/api/v1/auth/me — the caller's own account.
    router = private_router
