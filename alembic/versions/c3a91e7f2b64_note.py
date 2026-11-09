"""note — the reference CRUD module's table

Revision ID: c3a91e7f2b64
Revises: 8f2b1c4d9e07
Create Date: 2026-11-09 18:00:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op


# revision identifiers, used by Alembic.
revision: str = "c3a91e7f2b64"
down_revision: str | None = "8f2b1c4d9e07"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "note",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("code", sa.Uuid(), nullable=False),
        sa.Column("owner_code", sa.Uuid(), nullable=False),
        sa.Column("title", sa.String(length=200), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False
        ),
        sa.ForeignKeyConstraint(["owner_code"], ["auth.code"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.create_index(batch_op.f("ix_note_code"), ["code"], unique=True)
        batch_op.create_index(batch_op.f("ix_note_owner_code"), ["owner_code"], unique=False)


def downgrade() -> None:
    with op.batch_alter_table("note", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_note_owner_code"))
        batch_op.drop_index(batch_op.f("ix_note_code"))

    op.drop_table("note")
