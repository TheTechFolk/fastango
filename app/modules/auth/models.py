# app/modules/auth/models.py
import uuid

from sqlalchemy import String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import RoleType
from app.modules.common.models import CommonFieldBase


class Auth(CommonFieldBase):
    """A login identity: email, password, role.

    `is_active`, `created_at` and `updated_at` come from CommonFieldBase.
    """

    __tablename__ = "auth"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Public identifier and JWT subject, so the sequential primary key is never
    # exposed to clients. sqlalchemy.Uuid (not the postgresql dialect type)
    # renders natively on Postgres and as CHAR(32) on the SQLite test DB.
    code: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True),
        default=uuid.uuid4,
        nullable=False,
        unique=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    # bcrypt hash — never plaintext.
    password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=RoleType.USER.value,
        server_default=RoleType.USER.value,
    )
