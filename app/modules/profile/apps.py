# app/modules/profile/apps.py
from app.core.registry import ModuleConfig
from app.modules.profile.router import router


class ProfileConfig(ModuleConfig):
    name = "profile"
    router = router
    prefix = "/profile"
    tags = ["Profile"]
