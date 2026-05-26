# app/modules/common/models.py
from datetime import datetime

from sqlalchemy import Boolean, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TimeStampedBase(Base):
    """
    Abstract mixin that provides automatic created_at and updated_at timestamp
    columns on every table that inherits from it.
    """

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
    """
    Abstract mixin extending TimeStampedBase with a soft-delete is_active flag.
    This replicates the Django CommonFieldModel used across the original project.
    """

    __abstract__ = True

    is_active: Mapped[bool] = mapped_column(
        Boolean,
        default=True,
        server_default="true",
        nullable=False,
    )
