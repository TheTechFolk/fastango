# app/modules/auth/models.py
import uuid

from sqlalchemy import Boolean, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.modules.common.models import CommonFieldBase


class AdminAuth(CommonFieldBase):
    """
    Authentication record for a platform admin user.

    Moved to app/modules/auth/ — a shared, top-level auth module
    that is not coupled to any specific domain sub-directory.
    """

    __tablename__ = "admin_auth"

    id: Mapped[int] = mapped_column(primary_key=True, index=True, autoincrement=True)
    admin_code: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        default=uuid.uuid4,
        nullable=False,
        unique=True,
        index=True,
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_superuser: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, server_default="true")
