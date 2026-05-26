# app/modules/home/apps.py
from app.core.registry import ModuleConfig
from app.modules.home.router import router


class HomeConfig(ModuleConfig):
    name = "home"
    router = router
    prefix = "/home"
    tags = ["Home"]
