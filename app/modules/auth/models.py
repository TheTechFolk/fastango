# app/modules/auth/models.py
import uuid
from datetime import datetime

from sqlalchemy import DateTime, String, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.constants import RoleType
from app.database import Base
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


class RevokedToken(Base):
    """A refresh token that can no longer be redeemed — by logout or rotation.

    Only /refresh and /logout read this table, so revocation costs ordinary
    requests nothing. The trade-off: an access token already issued stays valid
    until it expires (JWT_ACCESS_TOKEN_EXPIRE_MINUTES), so keep that short.
    """

    __tablename__ = "revoked_token"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    # Unique, so inserting it is the check-and-revoke in one atomic step: two
    # concurrent refreshes with one token cannot both succeed.
    jti: Mapped[str] = mapped_column(String(64), nullable=False, unique=True, index=True)
    # ponytail: rows past expires_at are dead weight; delete them on a schedule
    # once the table grows (DELETE FROM revoked_token WHERE expires_at < now()).
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    # Insert-only, so no updated_at: when it was revoked is all there is to know.
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
