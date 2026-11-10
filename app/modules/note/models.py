# app/modules/note/models.py
import uuid

from sqlalchemy import ForeignKey, String, Text, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.common.models import TimeStampedBase


class Note(TimeStampedBase):
    """A note owned by one account. The reference CRUD table."""

    __tablename__ = "note"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Public identifier — the sequential primary key never leaves the database.
    code: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), default=uuid.uuid4, nullable=False, unique=True, index=True
    )
    # The string table name, not an import of Auth: that is what keeps this
    # module and auth independently deletable. It points at `auth.code` because
    # that is the access token's subject, so no lookup is needed to set it.
    owner_code: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("auth.code", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False, default="")
