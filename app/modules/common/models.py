# app/modules/common/models.py
"""Abstract ORM base classes shared by every module's tables.

Base classes only. A domain enum or a helper with one caller does not belong
here — it belongs with the module that owns it.
"""

from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimeStampedBase(Base):
    """Automatic created_at / updated_at on every table that inherits it."""

    __abstract__ = True

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=func.now(),
        onupdate=func.now(),
        server_default=func.now(),
        nullable=False,
    )


class CommonFieldBase(TimeStampedBase):
    """TimeStampedBase plus a soft-delete `is_active` flag."""

    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
