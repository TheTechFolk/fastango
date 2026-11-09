"""revoked_token — refresh tokens retired by logout or rotation

Revision ID: 8f2b1c4d9e07
Revises: 5ca7ea527fc1
Create Date: 2026-11-09 12:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8f2b1c4d9e07"
down_revision: str | None = "5ca7ea527fc1"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "revoked_token",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("jti", sa.String(length=64), nullable=False),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("revoked_token", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_revoked_token_jti"), ["jti"], unique=True)


def downgrade() -> None:
    with op.batch_alter_table("revoked_token", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_revoked_token_jti"))

    op.drop_table("revoked_token")
