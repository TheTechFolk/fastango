# app/modules/note/apps.py
from app.core.registry import ModuleConfig
from app.modules.note.router import router


class NoteConfig(ModuleConfig):
    """The reference CRUD module — copy its shape, then delete it.

    Removing it is `rm -r app/modules/note tests/modules/note` plus its
    migration in alembic/versions/.
    """

    name = "note"
    prefix = "/notes"
    tags = ["Notes"]

    # /private/api/v1/notes — every route needs a valid access token.
    router = router
